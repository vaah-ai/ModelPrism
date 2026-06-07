# Task M1-T8-P3 — Fix PrimeVue Icons (pi-* not visible)

> **Milestone:** M1 (Foundation)
> **Priority:** High
> **Status:** ⚪ Not Started
> **Parent:** M1-T8 (Nuxt Dashboard Scaffold)
> **Dependencies:** M1-T8 (Complete)

## Description

PrimeVue icons (`pi-*` classes) are used throughout the sidebar navigation, action buttons, summary cards, empty states, and status indicators but may not be visible because the PrimeVue icon stylesheet (`primeicons.css`) isn't imported.

## Root Cause

PrimeVue icons require the `primeicons` CSS to be loaded. With the `@primevue/nuxt-module` auto-import setup, icons may not be automatically included — the CSS layer needs to be explicitly imported.

## Scope

- Verify `primeicons` package is installed as a dependency
- Add `primeicons` CSS import in `main.css` or via `nuxt.config.ts` `css` array
- Verify all icon references render correctly:
  - Sidebar nav items: `pi pi-server`, `pi pi-box`, `pi pi-chart-bar`, `pi pi-key`, `pi pi-chart-line`, `pi pi-cog`, `pi pi-shield`
  - Action buttons: `pi pi-plus`, `pi pi-chevron-right`, `pi pi-copy`, `pi pi-times`, `pi pi-home`, `pi pi-arrow-left`
  - Status indicators: `pi pi-check-circle`, `pi pi-exclamation-triangle`, `pi pi-times-circle`, `pi pi-info-circle`
  - Empty states: `pi pi-server`
  - Loading spinner: `pi pi-spin pi-spinner`
- Fix any icons that still don't render after CSS import

## Acceptance Criteria

- [ ] `primeicons` package listed in `package.json` dependencies
- [ ] Icon CSS imported and all `pi-*` classes render visible glyphs
- [ ] Sidebar navigation icons display correctly
- [ ] Action button icons display correctly
- [ ] Summary card status icons display correctly
- [ ] Empty state icons display correctly
- [ ] Loading spinner renders and animates
- [ ] No icon-related console warnings or errors
