export const API = import.meta.env.VITE_API_URL || `http://${window.location.hostname}:8000`;
export function authHeaders() {
  const token = localStorage.getItem('access_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}
export async function memoryRequest(path = '', options = {}) {
  const response = await fetch(`${API}/memory${path}`, {
    ...options, headers: { 'Content-Type': 'application/json', ...authHeaders() },
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(response.status === 401 ? 'Please log in again to use your cooking memory.' : typeof data?.detail === 'string' ? data.detail : 'Could not update cooking memory. Please try again.');
  return data;
}
