import { apiClient, setAccessToken } from "./client";
import { getCookie } from "../lib/cookies";
import type { AccessTokenResponse, User } from "./types";

export async function registerRequest(email: string, password: string, fullName: string): Promise<User> {
  const { data } = await apiClient.post<AccessTokenResponse>("/auth/register", {
    email,
    password,
    full_name: fullName,
  });
  setAccessToken(data.access_token);
  return data.user;
}

export async function loginRequest(email: string, password: string): Promise<User> {
  const { data } = await apiClient.post<AccessTokenResponse>("/auth/login", { email, password });
  setAccessToken(data.access_token);
  return data.user;
}

export async function logoutRequest(): Promise<void> {
  const csrfToken = getCookie("csrf_token");
  await apiClient.post(
    "/auth/logout",
    {},
    { headers: csrfToken ? { "X-CSRF-Token": csrfToken } : {} },
  );
  setAccessToken(null);
}

export async function fetchCurrentUser(): Promise<User> {
  const { data } = await apiClient.get<User>("/auth/me");
  return data;
}
