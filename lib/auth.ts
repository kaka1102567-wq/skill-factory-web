import { cookies } from "next/headers";

const AUTH_COOKIE = "sf_auth";
const COOKIE_MAX_AGE = 7 * 24 * 60 * 60; // 7 days

export async function isAuthenticated(): Promise<boolean> {
  const cookieStore = await cookies();
  const token = cookieStore.get(AUTH_COOKIE);
  if (!token) return false;
  return token.value === getAuthToken();
}

export function getAuthToken(): string {
  const password = process.env.FACTORY_PASSWORD || "skillfactory2025";
  let hash = 0;
  for (let i = 0; i < password.length; i++) {
    const char = password.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash;
  }
  return `sf_${Math.abs(hash).toString(36)}`;
}

export function getAuthCookieConfig() {
  return {
    name: AUTH_COOKIE,
    value: getAuthToken(),
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    maxAge: COOKIE_MAX_AGE,
    path: "/",
  };
}
