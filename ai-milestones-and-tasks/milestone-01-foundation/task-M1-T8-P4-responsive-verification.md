# Task M1-T8-P4 — Responsive Verification

> **Milestone:** M1 (Foundation)
> **Priority:** Medium
> **Status:** ⚪ Not Started
> **Parent:** M1-T8 (Nuxt Dashboard Scaffold)
> **Dependencies:** M1-T8-P3 (Fix PrimeVue Icons)

## Description

Verify and fix the dashboard layout across mobile (375px), tablet (768px), and desktop (1280px+) viewports. The sidebar has a responsive overlay for <1024px but full verification hasn't been performed.

## Scope

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

- [ ] Mobile (375px): dashboard loads, sidebar toggle works, content is usable
- [ ] Tablet (768px): sidebar toggle works, DataTable is readable (may scroll horizontally)
- [ ] Desktop (1280px+): full sidebar visible, DataTable fills available width
- [ ] Sidebar overlay dismisses on outside click and nav item selection
- [ ] No horizontal overflow or clipped content on any viewport
- [ ] Touch targets are at least 44×44px on mobile
- [ ] Server detail page metric cards stack properly on mobile
