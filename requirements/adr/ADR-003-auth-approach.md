# ADR-003: Auth Approach

## Status
Accepted

## Context
Initial requirements listed `sidebase/nuxt-auth` for frontend authentication. However:

1. Sidebase/nuxt-auth expects Nuxt server route endpoints (`/api/auth/*`) with specific shapes
2. Our auth backend is FastAPI JWT — bridging them requires custom provider configuration
3. Nuxt 4 compatibility with sidebase/nuxt-auth is uncertain
4. Complex: dashboard uses JWT, agents use `mp_` tokens, proxy uses `sk-` keys — three auth flows sidebase doesn't understand
5. Sidebase adds significant complexity for what is a simple email/password flow

## Decision
- **Email/password only** — simple, no OAuth
- **Custom Pinia auth composable** — `useAuth()` calling FastAPI JWT endpoints directly
- JWT access token (15 min) + refresh token (7 day rotation)
- Tokens stored in httpOnly cookie for security
- Auth state managed in dedicated `stores/auth.ts` Pinia store

## Consequences
- No dependency on sidebase/nuxt-auth
- Full control over auth flow
- Frontend auth is ~200 lines of composable code instead of a complex module
- Three auth types (JWT, mp_token, sk_key) each have separate, simple implementations
