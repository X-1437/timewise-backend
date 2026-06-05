---
name: Chronos Precision
colors:
  surface: '#f7f9fb'
  surface-dim: '#d8dadc'
  surface-bright: '#f7f9fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f6'
  surface-container: '#eceef0'
  surface-container-high: '#e6e8ea'
  surface-container-highest: '#e0e3e5'
  on-surface: '#191c1e'
  on-surface-variant: '#464554'
  inverse-surface: '#2d3133'
  inverse-on-surface: '#eff1f3'
  outline: '#767586'
  outline-variant: '#c7c4d7'
  surface-tint: '#494bd6'
  primary: '#4648d4'
  on-primary: '#ffffff'
  primary-container: '#6063ee'
  on-primary-container: '#fffbff'
  inverse-primary: '#c0c1ff'
  secondary: '#006c4a'
  on-secondary: '#ffffff'
  secondary-container: '#82f5c1'
  on-secondary-container: '#00714e'
  tertiary: '#4b41e1'
  on-tertiary: '#ffffff'
  tertiary-container: '#645efb'
  on-tertiary-container: '#fffbff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e1e0ff'
  primary-fixed-dim: '#c0c1ff'
  on-primary-fixed: '#07006c'
  on-primary-fixed-variant: '#2f2ebe'
  secondary-fixed: '#85f8c4'
  secondary-fixed-dim: '#68dba9'
  on-secondary-fixed: '#002114'
  on-secondary-fixed-variant: '#005137'
  tertiary-fixed: '#e2dfff'
  tertiary-fixed-dim: '#c3c0ff'
  on-tertiary-fixed: '#0f0069'
  on-tertiary-fixed-variant: '#3323cc'
  background: '#f7f9fb'
  on-background: '#191c1e'
  surface-variant: '#e0e3e5'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 36px
    fontWeight: '700'
    lineHeight: 44px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  headline-sm:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.05em
  mono-sm:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  sidebar-width: 280px
  container-max-width: 1200px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 40px
  unit-xs: 4px
  unit-sm: 8px
  unit-md: 16px
  unit-lg: 24px
  unit-xl: 48px
---

## Brand & Style

The design system is engineered for a time-series data analysis assistant, prioritizing **Professionalism, Trust, and Intelligence**. The visual language is rooted in **Corporate Modernism** with subtle **Glassmorphism** accents to signify advanced AI capabilities. 

The personality is that of a "silent expert"—unobtrusive yet powerful. It uses a clean, systematic approach to data density, ensuring that complex temporal datasets remain legible and actionable. The aesthetic balances the stability of enterprise SaaS with the fluid, dynamic nature of real-time data analysis.

**Key Visual Principles:**
- **Clarity over Decoration:** Every element serves a functional purpose in the data storytelling process.
- **Precision:** High attention to alignment, consistent spacing, and crisp typography to mirror the accuracy of the underlying algorithms.
- **Calmness:** A cool-toned palette and generous whitespace reduce cognitive load during intense analytical tasks.

## Colors

The palette is anchored by a **Refined Indigo** primary, representing the depth of data and algorithmic intelligence. This is complemented by a **Sophisticated Emerald** for action-oriented elements (e.g., "New Analysis"), symbolizing growth and successful insights.

- **Primary (Indigo):** Used for brand identity, primary actions, and header backgrounds. The gradient moves from a vibrant indigo to a deep violet-indigo.
- **Secondary (Emerald):** Reserved for "Success" states and "Positive Growth" indicators in time-series charts, as well as the main "Create" button.
- **Neutrals:** A range of cool-toned greys (`#F8FAFC` to `#1E293B`) provides a professional foundation. Backgrounds utilize very light cool-grey tints to separate the sidebar from the main canvas without harsh borders.
- **Data Visualization:** Use a distinct categorical palette for line charts, ensuring high contrast against the neutral background.

## Typography

This design system uses **Inter** as its primary typeface due to its exceptional legibility in UI and data-heavy contexts. For specific technical data points or code snippets, **JetBrains Mono** is utilized.

- **Scale:** A tight scale is used to maintain a professional, information-dense environment.
- **Weight:** Semi-bold (600) is used for headers to create a clear hierarchy against the medium (500) and regular (400) body text.
- **Hierarchy:** Display sizes are reserved for onboarding and empty states. Main application views rely on `headline-md` for page titles and `body-sm` for sidebar navigation.
- **Localization:** When rendering Chinese characters (鸿溯), ensure the system falls back to `PingFang SC` or `Microsoft YaHei` while maintaining the specified weight and line-height.

## Layout & Spacing

The layout follows a **Fixed-Fluid Hybrid** model:
- **Sidebar:** A fixed-width (280px) vertical navigation bar on the left. It uses a subtle cool-grey background (`#F1F5F9`) to anchor the application.
- **Main Canvas:** A fluid area that expands to fill the remaining width, but caps content at 1200px for optimal readability of charts and tables.
- **Onboarding:** Centered layout within the main canvas, using large vertical spacing (`unit-xl`) to create an airy, welcoming "Home" feel.

**Grid:**
A 12-column grid is used for the main canvas. Elements like data cards and chart widgets should span 4, 6, or 12 columns.
- **Desktop:** 24px gutters, 40px margins.
- **Tablet:** 16px gutters, 24px margins.
- **Mobile:** Sidebar collapses into a hamburger menu; 16px margins for content.

## Elevation & Depth

Visual hierarchy is established through **Tonal Layers** and **Soft Ambient Shadows**.

- **Level 0 (Base):** The main canvas background (`#F8FAFC`).
- **Level 1 (Surface):** Cards, input fields, and the sidebar. These use a white background and a very subtle 1px border (`#E2E8F0`).
- **Level 2 (Raised):** Hover states for interactive cards and active dropdowns. These use a soft, diffused shadow: `0 4px 6px -1px rgb(0 0 0 / 0.05), 0 2px 4px -2px rgb(0 0 0 / 0.05)`.
- **Level 3 (Overlay):** Modals and context menus. These use a stronger shadow with a slight indigo tint to link back to the brand: `0 20px 25px -5px rgb(99 102 241 / 0.1)`.

**Glassmorphism:** The top navigation bar and sidebar active states use a light backdrop blur (8px) and 80% opacity to create a sense of modernity and depth.

## Shapes

The design system employs **Rounded** geometry (8px - 24px) to soften the technical nature of data analysis, making the tool feel approachable.

- **Standard (0.5rem / 8px):** Applied to buttons, input fields, and small UI widgets.
- **Large (1rem / 16px):** Applied to data cards, main containers, and the primary sidebar "Action" button.
- **Extra Large (1.5rem / 24px):** Used for large onboarding containers and decorative banner elements.
- **Pill:** Reserved exclusively for status indicators (tags/chips) to distinguish them from interactive buttons.

## Components

### Buttons
- **Primary Action:** Emerald gradient with white text. High-contrast. 12px rounded corners.
- **Secondary/Ghost:** Transparent background with Indigo border and text.
- **Sidebar Action:** Large, full-width buttons with left-aligned icons. Active state uses a light indigo background (`#EEF2FF`) and a 4px vertical "indicator" bar on the left.

### Input Fields
- **Search/Prompt Bar:** Large, white background with a soft 1px border. On focus, the border changes to Indigo with a subtle glow (2px spread).
- **File Upload:** A dedicated "drop zone" component with a dashed indigo border and a centered emerald icon.

### Cards & Widgets
- **Data Cards:** White background, 16px rounded corners, 1px border. Headlines use `headline-sm`.
- **Chart Containers:** No borders; defined by whitespace and subtle elevation if grouped.

### Chips & Tags
- **Status Tags:** Pill-shaped. Use low-saturation background tints (e.g., light green for "Complete") with high-saturation text for legibility.

### Sidebar Lists
- **Session Items:** Title on top (`body-sm`, bold), date below (`label-md`, muted grey). Active items use a subtle indigo tint.

### Data Tables
- Clean, borderless rows. Header row has a light grey background and uses `label-md` for column titles. Row hover uses a light blue tint.