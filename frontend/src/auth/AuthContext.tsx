import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { fetchCurrentUser, loginRequest, logoutRequest, registerRequest } from "../api/auth";
import { onSessionChange, restoreSession } from "../api/client";
import type { User } from "../api/types";

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Restore a session from the httpOnly refresh cookie on first load.
    // Stay in the loading state until that call settles so ProtectedRoute
    // cannot send the user to /login while refresh is still in flight.
    let cancelled = false;
    let restorationDone = false;

    const unsubscribe = onSessionChange((sessionUser) => {
      if (cancelled) return;
      // A failed overlapping refresh must not clear the user until this
      // boot restore has finished — otherwise Strict Mode / a second
      // refresh attempt can broadcast null and bounce to /login.
      if (!restorationDone && sessionUser === null) return;
      setUser(sessionUser);
    });

    restoreSession()
      .then((restoredUser) => {
        if (cancelled) return;
        restorationDone = true;
        setUser(restoredUser);
        setIsLoading(false);
      })
      .catch(() => {
        if (cancelled) return;
        restorationDone = true;
        setUser(null);
        setIsLoading(false);
      });

    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, []);

  const login = async (email: string, password: string) => {
    const loggedInUser = await loginRequest(email, password);
    setUser(loggedInUser);
  };

  const register = async (email: string, password: string, fullName: string) => {
    const registeredUser = await registerRequest(email, password, fullName);
    setUser(registeredUser);
  };

  const logout = async () => {
    try {
      await logoutRequest();
    } finally {
      // Clear client-side state regardless of whether the network call
      // succeeded — an already-invalid session shouldn't trap the user.
      setUser(null);
    }
  };

  const value: AuthContextValue = {
    user,
    isLoading,
    isAuthenticated: user !== null,
    login,
    register,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}

// Exported for completeness/future use (e.g. a manual "refresh my
// profile" action) — not currently called anywhere, since login/register/
// restoreSession already return the user.
export { fetchCurrentUser };
