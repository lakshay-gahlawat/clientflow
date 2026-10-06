import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import { getCookie } from "../lib/cookies";
import type { AccessTokenResponse, ApiErrorBody, User } from "./types";

const baseURL = import.meta.env.VITE_API_BASE_URL;
if (!baseURL) {
  console.error("VITE_API_BASE_URL is not set - rebuild after setting it.");
}

export const apiClient = axios.create({
  baseURL,
  withCredentials: true, // sends the httpOnly refresh cookie automatically
  timeout: 60_000, // Render free tier can take ~50s to wake up
});

// --- In-memory access-token store -------------------------------------
// Deliberately NOT localStorage/sessionStorage — kept in module memory
// only, per the backend's Phase 4 design (XSS can't read a JS variable
// out of a closure the way it can read storage). Lost on page reload by
// design; session is restored via /auth/refresh on app boot (see
// AuthContext), using the httpOnly refresh cookie.
let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

// --- Session-state broadcast -------------------------------------------
// The response interceptor can silently refresh (or fail to refresh) a
// session outside of any React event handler. AuthContext subscribes here
// so its `user` state stays truthful even when a refresh happens
// transparently mid-request, without the API client needing to know
// anything about React or routing.
type SessionListener = (user: User | null) => void;
const sessionListeners = new Set<SessionListener>();

export function onSessionChange(listener: SessionListener): () => void {
  sessionListeners.add(listener);
  return () => sessionListeners.delete(listener);
}

function broadcastSession(user: User | null): void {
  sessionListeners.forEach((listener) => listener(user));
}

// --- Request interceptor: attach the access token -----------------------
apiClient.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

// --- Response interceptor: transparent refresh-on-401 --------------------
// Only ONE refresh call may be in flight at a time. The backend rotates
// the refresh token on every use and treats replaying an already-rotated
// token as a theft signal — killing ALL sessions for that user (see
// Phase 4 auth_service.rotate_session). If two requests raced to refresh
// independently, the second would be using an already-revoked token and
// would nuke the very session the first refresh just established. This
// shared promise is what prevents that.
let refreshPromise: Promise<string | null> | null = null;

async function performRefresh(): Promise<string | null> {
  try {
    const csrfToken = getCookie("csrf_token");
    const { data } = await apiClient.post<AccessTokenResponse>(
      "/auth/refresh",
      {},
      {
        headers: csrfToken ? { "X-CSRF-Token": csrfToken } : {},
        // Marks this request so the response interceptor below doesn't
        // try to refresh-and-retry a failed refresh call itself.
        _isRefreshCall: true,
      } as InternalAxiosRequestConfig & { _isRefreshCall: true },
    );
    setAccessToken(data.access_token);
    broadcastSession(data.user);
    return data.access_token;
  } catch {
    setAccessToken(null);
    broadcastSession(null);
    return null;
  } finally {
    refreshPromise = null;
  }
}

declare module "axios" {
  export interface InternalAxiosRequestConfig {
    _isRefreshCall?: boolean;
    _retried?: boolean;
  }
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as InternalAxiosRequestConfig | undefined;

    if (
      error.response?.status === 401 &&
      config &&
      !config._isRefreshCall &&
      !config._retried
    ) {
      config._retried = true;
      refreshPromise ??= performRefresh();
      const newToken = await refreshPromise;

      if (newToken) {
        config.headers.Authorization = `Bearer ${newToken}`;
        return apiClient(config);
      }
    }

    return Promise.reject(error);
  },
);

// Called once on app boot (see AuthContext) to restore a session from
// the httpOnly refresh cookie, if one exists.
export async function restoreSession(): Promise<User | null> {
  // Strict Mode remounts AuthProvider and would otherwise rotate the
  // refresh cookie a second time. Reuse of the previous token is treated
  // as theft and kills the session — skip a second HTTP refresh when
  // this page load already restored successfully.
  if (accessToken && lastKnownUser) {
    return lastKnownUser;
  }
  refreshPromise ??= performRefresh();
  const token = await refreshPromise;
  return token ? getLastKnownUser() : null;
}

let lastKnownUser: User | null = null;
export function getLastKnownUser(): User | null {
  return lastKnownUser;
}
onSessionChange((user) => {
  lastKnownUser = user;
});

// --- Error message extraction -------------------------------------------
export function extractErrorMessage(error: unknown, fallback = "Something went wrong"): string {
  if (axios.isAxiosError(error)) {
    const body = error.response?.data as ApiErrorBody | undefined;
    if (typeof body?.detail === "string") return body.detail;
    if (Array.isArray(body?.detail) && body.detail.length > 0) {
      return body.detail.map((d) => d.msg).join("; ");
    }
        if (error.code === "ECONNABORTED") {
      return "The server is waking up - please try again in a moment.";
    }
    if (!error.response) {
      return "Can't reach the server — check your connection and try again.";
    }
  }
  return fallback;
}
