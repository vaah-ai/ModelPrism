# F2: Frontend Scaffolding

## Metadata
- **ID:** F2
- **Phase:** Foundation
- **Effort:** Medium
- **Dependencies:** None
- **Acceptance Criteria Count:** 5

## Description
Initialize the Nuxt 4 frontend application with PrimeVue 4, Tailwind CSS v4, and Pinia. Set up the project structure (layouts, pages scaffold, composable directories), configure the Nuxt module ecosystem (PrimeVue auto-import, Tailwind, Pinia), establish the base HTTP client for the FastAPI JSON:API backend, and provide a mock-ready authentication composable so subsequent auth, dashboard, and deployment feature work can proceed in parallel.

## Concrete Examples (Specification by Example)

### Example 1: Scaffold Install and Dev Server
- **Input:** Running `pnpm install && pnpm dev` in the `frontend/` directory of a freshly cloned repository.
- **Action:** Nuxt 4 starts with the correct modules loaded. The application renders the default layout shell, which shows a loading spinner and then redirects to `/login` because no session cookie or stored JWT exists. The dev server is available at `http://localhost:3000`.
- **Expected Output:** The browser displays a `<div id="__nuxt">` containing a full-width PrimeVue `Toast` container, a centered `Card` with a login form (email + password inputs, "Sign In" button), and a link to `/register`. The console logs no unhandled errors, and `pnpm dev` shows a clean HMR-ready compilation log with no warnings about missing modules or plugin conflicts.

### Example 2: Login Form Submits Correct API Call
- **Input:** User fills in `admin@modelprism.io` / `password123` on the login page (backing mock server or real backend at `http://localhost:8000`) and clicks "Sign In".
- **Action:** The `useAuth` Pinia store's `login()` action sends a `POST /api/auth/login` request with `Content-Type: application/json` and body `{"email": "admin@modelprism.io", "password": "password123"}` via the Nuxt `$fetch` client configured with `baseURL: "http://localhost:8000"`.
- **Expected Output:** The request includes `credentials: "include"` so cookies are forwarded. If the server returns `{"access_token": "...", "refresh_token": "..."}` with HTTP 200, the store stores both tokens in Pinia state (and optionally in `localStorage` via `useStorage`), sets an Axios-like authorization header on the HTTP client, and calls `navigateTo("/dashboard")`. If the server returns HTTP 401, a PrimeVue `Message` with `severity="error"` appears above the form: "Invalid email or password."

### Example 3: Dashboard Layout Routing
- **Input:** User navigates to `/dashboard` while authenticated.
- **Action:** The `dashboard.vue` layout activates, which enforces authentication via the middleware guard. It renders a vertical `PanelMenu` sidebar (PrimeVue) containing navigation items: Servers, Models, Benchmarks, API Keys, Usage, Settings, Admin.
- **Expected Output:** The sidebar is visible on the left (collapsible on screens narrower than 1024px). The main content area to the right renders the matched child page component (e.g., `dashboard/index.vue` — the GPU server overview). A top navbar shows the workspace name and a user avatar dropdown with items: Settings, Sign Out.

### Example 4: Auth Middleware Redirects Unauthenticated Users
- **Input:** An unauthenticated user navigates directly to `/dashboard/servers/abc-123` in the browser address bar.
- **Action:** The `auth` middleware (defined in `middleware/auth.ts`) checks the Pinia auth store for a valid JWT. If no token exists or the token is expired, the middleware records the intended route as a query parameter (`?redirect=/dashboard/servers/abc-123`) and calls `abortNavigation()` followed by `navigateTo("/login")`.
- **Expected Output:** The browser URL changes to `http://localhost:3000/login?redirect=%2Fdashboard%2Fservers%2Fabc-123`. The login form appears. After successful login, the `useAuth` store reads the `redirect` query parameter (or defaults to `/dashboard`) and navigates there via `navigateTo()`.

### Example 5: Layout Breakpoint and Mobile Behavior
- **Input:** A user on a 768px-wide viewport opens the dashboard.
- **Action:** Tailwind's responsive utilities detect the viewport width. The dashboard layout switches to mobile mode: the sidebar is hidden by default. A hamburger icon appears in the top navbar. Clicking it opens an overlay sidebar (PrimeVue `Sidebar` component, `position="left"`) with the same navigation items.
- **Expected Output:** The main content area occupies the full viewport width. Tapping the hamburger icon slides the sidebar in from the left. Tapping outside the sidebar or selecting a navigation item dismisses it. All page content renders correctly without horizontal overflow at 768px.

## Acceptance Criteria

- **ACF2-1: Nuxt 4 project compiles and runs** — Running `pnpm install && pnpm dev` in `frontend/` produces a successful build with zero errors or warnings related to module configuration. The dev server binds to `localhost:3000` and serves the default landing page without crashing on route transitions.
- **ACF2-2: PrimeVue and Tailwind CSS are configured and rendered** — A minimal test page that includes a PrimeVue `Button`, `InputText`, `Card`, and `PanelMenu` component renders with correct PrimeVue styling (Aura theme), and custom Tailwind utility classes (e.g., `bg-surface-50`, `text-primary`) apply as expected. No CSS conflicts appear between PrimeVue and Tailwind.
- **ACF2-3: HTTP client targets the FastAPI backend** — The frontend's base HTTP client (via Nuxt's `$fetch` with a configured `baseURL`) successfully makes a `GET /api/health` request to `http://localhost:8000` and parses the JSON:API response, or falls back to mock data when the backend is unreachable, without throwing a CORS error. The client is available as a typed composable (`useApi()`) that all store actions and page components import.
- **ACF2-4: Auth middleware protects dashboard routes** — Navigating to any `/dashboard/*` URL without a stored JWT redirects to `/login` with a `?redirect=` query parameter preserving the original destination. Navigating to `/login` or `/register` while authenticated redirects to `/dashboard`. The middleware reads token expiry from the JWT payload and triggers a silent refresh attempt before resorting to full redirect.
- **ACF2-5: All page stubs exist and render without error** — Every page listed in the directory structure (`/`, `/login`, `/register`, `/pricing`, `/dashboard/index`, `/dashboard/servers/[id]`, `/dashboard/models/index`, `/dashboard/models/deploy`, `/dashboard/models/[id]`, `/dashboard/benchmarks/index`, `/dashboard/benchmarks/new`, `/dashboard/benchmarks/[id]`, `/dashboard/keys/index`, `/dashboard/usage/index`, `/dashboard/settings/index`, `/dashboard/settings/members`, `/dashboard/settings/billing`, `/dashboard/admin/index`) exists as a `.vue` file with a placeholder component and renders without throwing an unhandled error during navigation. Internal pages show a consistent "Coming soon" placeholder card.

## Technical Notes

- **Nuxt 4 project init:** Use `npx nuxi@latest init frontend`. Select TypeScript, Pinia, and Tailwind CSS during scaffolding. Add PrimeVue via `npx nuxi@latest module add primevue`. Configure in `nuxt.config.ts` with `primevue: { usePrimeVue: true, autoImport: true, components: { include: ['Button', 'InputText', 'Card', 'PanelMenu', 'Sidebar', 'Toast', 'Message', 'Avatar', 'Menubar', 'InputSwitch'] } }`. Apply the Aura theme: `@import "primevue/resources/themes/aura-light-blue/theme.css"` in `app.vue` or a global CSS file.

- **Tailwind v4 in Nuxt 4:** Tailwind v4 uses CSS-first configuration (`@import "tailwindcss"` in the main CSS file). Custom design tokens (colors, spacing) use `@theme` directives. The PrimeVue Tailwind preset is **not** used — styling relies on PrimeVue's built-in theming (Aura) plus custom Tailwind utilities for layout and spacing only, to avoid style conflicts documented in primevue/issues/5984.

- **Directory structure alignment:** The page scaffolding at `app/pages/` must exactly match the directory structure documented in `07-directory-structure.md`. Use `server/api/auth/session.get.ts` as the sole Nitro server route — all other API calls go directly to the FastAPI backend (no Nitro proxying needed).

- **HTTP client (`useApi` composable):** Create `/app/composables/useApi.ts` that wraps Nuxt's `useFetch`/`$fetch` with:
  - `baseURL` pointing to the FastAPI backend (default `http://localhost:8000`, configurable via `NUXT_PUBLIC_API_BASE` env var).
  - Automatic `Authorization: Bearer <token>` header injection from the Pinia auth store.
  - `credentials: "include"` for cookie forwarding.
  - Default `Accept: application/vnd.api+json` header for dashboard endpoints.
  - A response interceptor that catches HTTP 401 and triggers the auth store's `refresh()` action before retrying once.
  - A fallback path: if the backend is unreachable (network error), return mock data from a `/app/composables/mock/` directory so UI development can proceed without the backend running.

- **Auth composable (`useAuth` composable + `auth` store):** Create `/app/composables/useAuth.ts` as a thin wrapper around the `/app/stores/auth.ts` Pinia store.
  - Store actions: `login(email, password)`, `register(email, password)`, `logout()`, `refresh()`.
  - Store state: `user` (nullable user object), `accessToken` (string | null), `refreshToken` (string | null), `isAuthenticated` (computed boolean).
  - Token persistence: `useStorage('auth-tokens', { accessToken: null, refreshToken: null })` from VueUse for page-refresh resilience.
  - On app initialization (`app.vue` `onMounted` or Nuxt `plugin`), hydrate the store from local storage and attempt a token refresh if the stored access token looks expired.

- **Auth middleware (`middleware/auth.ts`):** A global or per-route middleware that:
  - Reads `isAuthenticated` from the Pinia auth store.
  - If the user is on `/login` or `/register` and already authenticated → `navigateTo('/dashboard')`.
  - If the user is on a `/dashboard/*` route and NOT authenticated → record `to.fullPath` as the `redirect` parameter, then `navigateTo('/login?redirect=' + encodeURIComponent(to.fullPath))`.
  - Uses `abortNavigation()` to prevent the protected page from rendering during the redirect.

- **Layout structure:**
  - `layouts/default.vue` — Landing page layout: centered content area, minimal navigation bar with logo + login/register links, no sidebar. Used by `/`, `/login`, `/register`, `/pricing`.
  - `layouts/dashboard.vue` — Authenticated layout: vertical sidebar (collapsible), top navbar with workspace/user info, `<slot />` for child pages. PrimeVue `PanelMenu` in the sidebar. `Toast` component mounted globally for notifications. Mobile-responsive: sidebar becomes an overlay at `<1024px` via Tailwind `lg:` breakpoint.

- **Error handling setup:** Create `error.vue` at `app/` root level to catch Nuxt errors (404, 500, unhandled exceptions). It should render a PrimeVue `Card` with the error message and a "Go Home" button, styled consistently with the rest of the app. Do NOT use Nuxt's default error page.

- **Integration point — F5 (Email/password auth):** This scaffolding provides the auth store, `useAuth` composable, and login/register page stubs. Feature F5 (`feature-f5-auth.md`) will wire up the actual API calls, JWT refresh logic, and session persistence.

- **Integration point — F14 (GPU server overview) and F15 (Single server dashboard):** The dashboard layout, sidebar navigation, and `useApi` composable scaffolded here will be populated with real data, charts, and live metric streams in features F14 (`feature-f14-gpu-server-overview.md`) and F15 (`feature-f15-single-server-dashboard.md`). F14 depends on the dashboard layout and auth middleware provided here; F15 additionally consumes the `useApi` HTTP client for JSON:API data fetching.

- **Mock data:** Place mock JSON:API responses in `app/composables/mock/` for each resource type (agent, model, benchmark, key, usage). Each mock module exports a function that returns a `Promise` resolving to a fake JSON:API `Document` so feature development does not block on backend availability.
