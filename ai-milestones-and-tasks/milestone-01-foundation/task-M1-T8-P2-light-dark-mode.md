# Task M1-T8-P2 — Light & Dark Mode Toggle

> **Milestone:** M1 (Foundation)
> **Priority:** Medium
> **Status:** 🟢 Complete
> **Parent:** M1-T8 (Nuxt Dashboard Scaffold)
> **Dependencies:** M1-T8-P1 (UI/UX Polish)

## Description

Add a theme toggle button in the top bar that lets users switch between light and dark mode manually, while respecting the system preference on first visit.

## Current State

- `nuxt.config.ts` has `darkModeSelector: 'system'` — dark mode works automatically but there's no way to override it
- PrimeVue auto-applies `p-dark` class when system preference is dark
- Components use `dark:` Tailwind variants but they haven't been verified

## Scope

- Add theme toggle button (sun/moon icon) in the top bar
- Store preference in localStorage via `useStorage('theme-preference', 'system')`
- On first visit, respect system preference (`prefers-color-scheme`)
- When user toggles, override system preference and persist the choice
- Ensure all component styles render correctly in both modes

## Acceptance Criteria

- [ ] Theme toggle button visible in top bar
- [ ] Toggle cycles: system → light → dark → system
- [ ] Preference persisted in localStorage across page reloads
- [ ] System preference respected on first visit
- [ ] All pages render correctly in light and dark mode
- [ ] Smooth transition between modes
