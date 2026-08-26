# Design values


The single source of truth for this skill. Edit this section to adapt it to your own design system.

**Fonts:** Geist, Manrope, Geist Mono, Poppins. Never Inter, Roboto, Arial, Open Sans, Helvetica. No italics. No weights above bold.

**Dark backgrounds:** `#000000` · `#181818` · `#1F1F1F` · `#272727` · `#313131` · `#131209`

**Hero heading gradient:** dark theme `#FFFFFF` → `#9B9B9B`; light theme `#000000` → `#666666`. Left to right, text only.

**Spacing:** 0, 2, 4, 8, 12, 16, 24, 32, 40, 48, 64, 80, 96px. Main buttons 8px vertical, 12px horizontal.

**Radius:** Tailwind values only. Nested shapes under a 32px gap use `inner = outer − gap`, applied only when the result exceeds 2.

**Icons:** Phosphor, Solar, Iconamoon.

**Motion:** `transition-all duration-700 ease-[cubic-bezier(0.32,0.72,0,1)]`. Scroll reveals 800ms or longer via `IntersectionObserver`.

**Type scale:** Tailwind default.

| Class | Size | Line height |
|---|---|---|
| `text-xs` | 12px | 16px |
| `text-sm` | 14px | 20px |
| `text-base` | 16px | 24px |
| `text-lg` | 18px | 28px |
| `text-xl` | 20px | 28px |
| `text-2xl` | 24px | 32px |
| `text-3xl` | 30px | 36px |
| `text-4xl` | 36px | 40px |
| `text-5xl` | 48px | 1 |
| `text-6xl` | 60px | 1 |
| `text-7xl` | 72px | 1 |
| `text-8xl` | 96px | 1 |
| `text-9xl` | 128px | 1 |
