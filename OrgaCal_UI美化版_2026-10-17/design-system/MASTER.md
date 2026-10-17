# OrgaCal UI design system

Source: the latest application document and figure atlas, figure 3 (2026-10-17).

## Direction

A scientific workbench, with a navy instrument header, stable left navigation,
teal actions, and input and result columns. On phones navigation becomes a
two-row grid and the input/result columns stack. Report export has a persistent
navigation entry. The first viewport offers an editable calculation, not a
marketing hero.

## Tokens

- Navy #16324F: identity and headings.
- Teal #0E7C86: action, selection and calculated scales.
- Pale teal #E6F2F3: selected navigation and context.
- Background #F7F9FA, white #FFFFFF: work surface.
- Text #1E2A33; secondary #526674: readable labels and explanations.
- Border #D8E1E6; input border #A7B8C4: structure and controls.
- Amber ink #AD511A on #FFF5E9: assumptions and evidence limitations.
- Dark theme has its own tokens in assets/workbench.css.

Typography: Aptos for Latin, Microsoft YaHei / PingFang SC for Chinese, installed
system fallbacks; no external font downloads. Headings 26/18 px, main text
15–16 px, explanatory text 13 px. Numeric controls use tabular figures.

## Layout and interaction

Desktop: a 194 px navigation rail and a flexible work area. Tables scroll inside
their own component. Photos retain their aspect ratio. Forms have visible
labels and units; advanced settings and long evidence are collapsible. Real
calculated values appear only after calculation; initial results explain the
next action. Native Gradio controls and keyboard behavior are retained. Visible
focus, 44 px actions and reduced-motion support are required.

## Brief review

The UI skill's initial database match (neumorphism / single-column landing)
did not fit this product. A narrower search matched the data-dense dashboard
style. Its enterprise landing pattern, orange palette and Fira typography were
not adopted: the user's supplied UI figure has priority.

The figure's 14 mPa threshold, 12.6 mPa result, disturbance contributions, ICC,
PC1 and candidate scores are demonstrations. They must never appear as live
results of functionality that has not been implemented. The present physics
model supports orbital shakers; advanced disturbance models, ICC, PDF ingestion
and biological surrogate optimization remain separate development work.
