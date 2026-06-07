# Task M1-T8-P3/P4 — Fix PrimeVue Icons + Responsive Verification

> **Milestone:** M1 (Foundation)
> **Priority:** High
> **Status:** 🔵 In Progress (combined)
> **Parent:** M1-T8 (Nuxt Dashboard Scaffold)
> **Dependencies:** M1-T8 (Complete)

## Description

Two small follow-up tasks merged into one: (1) fix PrimeVue icons (`pi-*` classes) that aren't rendering because `primeicons.css` is missing, and (2) verify and fix the dashboard layout across mobile (375px), tablet (768px), and desktop (1280px+) viewports.

## Part 1 — Fix PrimeVue Icons

### Root Cause

PrimeVue icons require the `primeicons` CSS to be loaded. With the `@primevue/nuxt-module` auto-import setup, icons may not be automatically included — the CSS layer needs to be explicitly imported.

### Part 1 Scope

- Verify `primeicons` package is installed as a dependency
- Add `primeicons` CSS import in `main.css` or via `nuxt.config.ts` `css` array
- Verify all icon references render correctly:
  - Sidebar nav items: `pi pi-server`, `pi pi-box`, `pi pi-chart-bar`, `pi pi-key`, `pi pi-chart-line`, `pi pi-cog`, `pi pi-shield`
  - Action buttons: `pi pi-plus`, `pi pi-chevron-right`, `pi pi-copy`, `pi pi-times`, `pi pi-home`, `pi pi-arrow-left`
  - Status indicators: `pi pi-check-circle`, `pi pi-exclamation-triangle`, `pi pi-times-circle`, `pi pi-info-circle`
  - Empty states: `pi pi-server`
  - Loading spinner: `pi pi-spin pi-spinner`
- Fix any icons that still don't render after CSS import

## Part 2 — Responsive Verification

### Part 2 Scope

- Test with Playwright browser emulation at 375px (mobile), 768px (tablet), 1280px (desktop)
- Verify flows:
  - Index → dashboard redirect on mobile
  - Sidebar toggle (hamburger button) on mobile/tablet
  - DataTable horizontal overflow on narrow screens
  - Summary cards stacking in 1-column grid on mobile
  - Server detail page layout on tablet/mobile
- Fix any layout breakage, overflow, or tap-target sizing issues
- Ensure sidebar overlay dismisses correctly when clicking outside or selecting a nav item

## Acceptance Criteria

- [ ] `primeicons` package listed in `package.json` dependencies
- [ ] Icon CSS imported and all `pi-*` classes render visible glyphs
- [ ] Sidebar navigation icons display correctly
- [ ] Action button icons display correctly
- [ ] Summary card status icons display correctly
- [ ] Empty state icons display correctly
- [ ] Loading spinner renders and animates
- [ ] No icon-related console warnings or errors
- [ ] Mobile (375px): dashboard loads, sidebar toggle works, content is usable
- [ ] Tablet (768px): sidebar toggle works, DataTable is readable (may scroll horizontally)
- [ ] Desktop (1280px+): full sidebar visible, DataTable fills available width
- [ ] Sidebar overlay dismisses on outside click and nav item selection
- [ ] No horizontal overflow or clipped content on any viewport
- [ ] Touch targets are at least 44×44px on mobile
- [ ] Server detail page metric cards stack properly on mobile
