# Task M1-T8-P1 — UI/UX Polish (Design Skills)

> **Milestone:** M1 (Foundation)
> **Priority:** Medium
> **Status:** 🟢 Complete
> **Parent:** M1-T8 (Nuxt Dashboard Scaffold)
> **Dependencies:** M1-T8 (Complete)

## Description

Refine the dashboard's visual design, spacing, typography, and component styling by invoking `ui-ux-pro-max` and `frontend-design` skills. This is a design improvement pass over the scaffolded structure.

## Scope

- Invoke `ui-ux-pro-max` skill to audit and suggest improvements for layout, visual hierarchy, typography scale, spacing consistency
- Invoke `frontend-design` skill to refine PrimeVue component styling and overall aesthetic
- Apply improvements to: dashboard layout, sidebar, top bar, summary cards, DataTable, empty states, server detail page
- No new functionality — visual refinement only

## Design Decisions (Approved)

- **Direction:** Bold & Tech-forward (dark-first, GPU-inference platform energy)
- **Primary Accent:** Cyan (#06b6d4 / cyan-500) — buttons, active nav, links, progress bars
- **Sidebar Style:** Same background as content area (gray-900 dark / white light), separated by 1px border — clean, modern (Nuxt UI Pro style)
- **Typography:** System font stack (Inter/system-ui) — no custom font load
- **Dark Theme Base:** Page bg gray-950, card/surface bg gray-900, elevated (dialogs) gray-800, borders gray-800
- **Light Theme Base:** Page bg surface-50, card bg white, borders surface-200
- **Text Hierarchy:** Primary white/gray-900, Secondary gray-400/gray-500, Muted gray-600/gray-400

## Acceptance Criteria

- [ ] Visual design audit completed via designated skills
- [ ] Design token system established (CSS custom properties + PrimeVue theme override)
- [ ] Bold & Tech-forward dark-first styling applied (Cyan accent, system font)
- [ ] Sidebar updated: same-level bg as content, 1px separator, active nav items highlighted with cyan
- [ ] Top bar refined: consistent with design tokens, better visual hierarchy for page title
- [ ] Summary cards improved: hover effects, consistent spacing, icon styling
- [ ] DataTable polished: header styling, row hover, row stripe colors, paginator styling
- [ ] Empty state visually enhanced: inline with dark theme
- [ ] Server detail page: polished metric cards, consistent card borders/backgrounds
- [ ] Error page styled: aligned with design tokens
- [ ] Consistent spacing and typography across all pages
- [ ] Improved visual hierarchy across DataTable, summary cards, and sidebar
- [ ] No regressions in existing functionality
