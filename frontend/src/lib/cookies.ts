// The CSRF cookie is deliberately NOT httpOnly (see backend Phase 4 design)
// so the frontend can read it and echo it back as a header — that's the
// double-submit pattern. It is set with Path=/ so it is visible on SPA
// routes like /dashboard. This is the only cookie we ever read from JS;
// the refresh token cookie is httpOnly, scoped to /api/v1/auth, and
// invisible to this code, by design.
export function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]!) : null;
}
