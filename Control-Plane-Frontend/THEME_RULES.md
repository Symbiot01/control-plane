# Systemic Clarity - Global Theme Rules

This repository strictly adheres to the "Systemic Clarity" design system. Any new UI components or layouts MUST follow these rules:

## 1. Aesthetic Environment
- The application operates in a **Dark Mode Environment** ("Corporate Modernism").
- Avoid generic colors. Use the specific deep charcoal and navy grays for surfaces to prevent eye strain and establish hierarchy.

## 2. Colors
Use the CSS variables defined in `src/index.css` or Tailwind classes (e.g., `bg-surface-container-low`, `text-on-surface`).
- **Primary**: `bg-primary` (`#1a73e8`) for primary CTAs and active states. Text on primary is `#ffffff`.
- **Background**: `bg-background` (`#101418`).
- **Surface**: Use the surface containers for hierarchy:
  - Base background: `bg-background` (`#101418`).
  - Cards/Containers: `bg-surface-container` (`#1c2024`) or `bg-surface-container-lowest` (`#0a0f13`).
  - Hover states: `bg-surface-container-low` or `bg-surface-container-high`.
- **Borders**: `border-outline-variant` (`#414754`).

## 3. Typography
- **Font**: Inter.
- Ensure you are using the mapped typography utility classes from Tailwind config:
  - `text-display-lg`, `text-headline-lg`, `text-title-md`, `text-body-md`, `text-body-sm`, `text-label-md`.

## 4. Spacing Grid
- Strict **8px** base fluid grid.
- Do not use arbitrary spacing (e.g., `mt-[5px]`). Rely on the configured Tailwind spacing (`m-xs`, `p-sm`, `gap-md`, `gap-lg`).
  - `xs`: 4px
  - `base`: 8px
  - `sm`: 12px
  - `md`: 16px
  - `lg`: 24px
  - `xl`: 32px

## 5. Shapes & Soft Geometry
- Default border radius for standard UI components (inputs, buttons, cards) is **8px** (`rounded-lg`).
- Small items (checkboxes): `2px` (`rounded-sm`).
- Medium items: `12px` (`rounded-xl`).
- Large containers: `16px`.
- Pills (tags, FABs): `9999px` (`rounded-full`).

## 6. Components
- **Inputs**: Outlined with `border-outline-variant`. On focus, the border thickens and changes to `border-primary` (`#1a73e8`).
- **Buttons**:
  - Primary: Solid `bg-primary` with `text-on-primary-container`.
  - Secondary/Outline: Border `border-outline-variant` with `text-primary`.
- **Cards**: Background `bg-surface-container` (`#1c2024`), border `border-outline-variant/30`, radius `rounded-lg` (8px).
