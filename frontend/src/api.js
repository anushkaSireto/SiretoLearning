const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
const TOKEN_STORAGE_KEY = "invoice_access_token";

export function setAccessToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_STORAGE_KEY, token);
    return;
  }
  localStorage.removeItem(TOKEN_STORAGE_KEY);
}

function getAccessToken() {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

async function request(path, options = {}) {
  const token = getAccessToken();
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });

  if (!response.ok) {
    let message = "Request failed";
    try {
      const payload = await response.json();
      message = payload.detail || message;
    } catch {
      message = response.statusText || message;
    }
    throw new Error(message);
  }

  if (response.status === 204) {
    return null;
  }
  return response.json();
}

export function fileUrl(path) {
  return `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
}

export function listInvoices() {
  return request("/api/invoices");
}

export function getInvoice(id) {
  return request(`/api/invoices/${id}`);
}

export function uploadInvoice(file) {
  const body = new FormData();
  body.append("file", file);
  return request("/api/invoices/upload", { method: "POST", body });
}

export function updateInvoice(id, payload) {
  return request(`/api/invoices/${id}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function deleteInvoice(id) {
  return request(`/api/invoices/${id}`, { method: "DELETE" });
}
