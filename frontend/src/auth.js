import Keycloak from "keycloak-js";
import { setAccessToken } from "./api";

const keycloak = new Keycloak({
  url: import.meta.env.VITE_KEYCLOAK_URL || "http://localhost:8080",
  realm: import.meta.env.VITE_KEYCLOAK_REALM || "Invoice-system",
  clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID || "invoice-client",
});

let initialized = false;

export async function initAuth() {
  if (initialized) {
    return keycloak;
  }

  const authenticated = await keycloak.init({
    onLoad: "login-required",
    pkceMethod: "S256",
    checkLoginIframe: false,
  });

  initialized = true;
  setAccessToken(authenticated ? keycloak.token : null);
  return keycloak;
}

export async function refreshToken() {
  if (!keycloak.authenticated) {
    setAccessToken(null);
    return null;
  }

  await keycloak.updateToken(30);
  setAccessToken(keycloak.token);
  return keycloak.token;
}

export function logout() {
  setAccessToken(null);
  return keycloak.logout({
    redirectUri: window.location.origin,
  });
}

export function getUserProfile() {
  return {
    name: keycloak.tokenParsed?.name || keycloak.tokenParsed?.preferred_username || "User",
    email: keycloak.tokenParsed?.email || "",
  };
}
