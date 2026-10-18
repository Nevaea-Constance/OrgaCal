# OrgaCal UI design system

Source: the supplied OrgaCal logo and its four-colour brand palette, plus
OrgaCal_境算师_申报书结构优化版(3).docx (2026-10-18).

## Direction

A precise, approachable laboratory workbench. The original green/coral logo
anchors a compact white masthead. Deep green type, light sage work surfaces,
teal structure and restrained warm coral cues connect the interface to the
organoid motif. Stable left navigation and input/result columns remain. On
phones navigation becomes a two-row grid and the columns stack. The first
viewport prioritizes the current scientific task and usable inputs/results.

## Tokens

- Brand ink #123B36: identity, headings and main text.
- Brand primary #2E8B7F: structure, selection indicators and plotted ranges.
- Brand accent #E8836B: highlights and contextual emphasis.
- Brand flesh #F4C9B8: gentle cell-related or supporting warm tones.
- Action/link ink #246E65: darker teal for white-button/text contrast.
- Pale green #E5F2ED: selected navigation and context.
- Background #F3F7F4, white #FFFFFF: work surfaces.
- Secondary text #516B61; border #D2E1D9; control boundary #829D92.
- Evidence/assumption notice: #8F3F2C text on #FFF0E9 with a coral edge.
- Never put small white text on the supplied coral or primary teal; use
  contrast-tested darker teal action fills or green ink on the warm tones.
- Dark mode uses green surfaces #0E211E/#152E29, light text #E8F3EE,
  secondary #B7D1C5, accessible light teal action fills and light coral ink.
  The masthead remains white so the original dark-green logo is never altered.

Semantic CSS variables are --oc-ink, --oc-primary, --oc-primary-ink,
--oc-accent, --oc-flesh, --oc-warning-ink, --oc-warning, --oc-text,
--oc-muted, --oc-bg, --oc-surface, --oc-pale, --oc-line and --oc-control.
The fixed supplied palette uses --oc-brand-ink/primary/accent/flesh; it does not
change with the theme. Gradio's theme uses the same values for native controls.

Typography: Aptos for Latin, Microsoft YaHei / PingFang SC for Chinese, installed
system fallbacks; no external font downloads. Headings 25/18 px, main text
15–16 px, explanatory text 13 px. Numeric controls use tabular figures.

## Layout and interaction

Desktop: a 184 px navigation rail and a flexible work area. Tables scroll inside
their own component. Photos retain their aspect ratio. Forms have visible
labels and units; advanced settings and long evidence are collapsible. Real
calculated values appear only after calculation; initial results explain the
next action. Native Gradio controls and keyboard behavior are retained. Visible
focus, 44 px actions and reduced-motion support are required. The masthead is
compact to leave useful results visible in screenshots. White space separates
tasks; boundaries indicate actual form/result groups. Warm emphasis is limited
to notices, brand markers and meaningful distinctions, not decorative cards.

The logo is the unchanged supplied assets/logo.png, embedded as a data URI so
cloud hosting does not depend on a separate static-file route. It retains its
aspect ratio and the text alternative "OrgaCal 境算师". It must be included when
rebuilding the public resource bundle.

## Refinement pass (frontend-design skill, 2026-10-18)

- Radius scale replaces one-size-fits-all rounding: --oc-r-panel 10 px,
  --oc-r-control 6 px, --oc-r-chip 4 px. Hierarchy now shows in the shape.
- Result panels carry a faint pale-green wash at the top so results read apart
  from input panels; the shear range bar uses the darker action teal, a 10%
  grid and a surface-coloured halo so the range reads as a measured interval.
- Copy: removed middle-dot meta strings in the masthead and footer. The motto no
  longer says "找安全区"; it says "查条件交集", matching the evidence boundary.
- Header tag and motto raised to 12/14 px for legibility.

- Literature, DOI/PDF and screening-scan panels use gr.Column with oc-panel,
  not gr.Group. Group paints its container in the border colour, which showed as
  hard green bars between the heading and the inputs.
- Selected navigation uses the coral accent edge (logo's warm colour) so teal
  and coral share the interface, as they do in the logo.
- Dark mode moves from saturated green surfaces to a softer neutral charcoal
  with a slight green cast: bg #171B1A, surface #1F2524, line #38433F, text
  #EAEFEC, muted #AEBBB5, pale #2A3A35. Teal and coral stay as accents only.

## Brief review

The UI skill's initial "scientific workbench dashboard" system match
(neumorphism / single-column landing) did not fit this product. The explicit
"data dense dashboard" style query verified a data-oriented layout with stable
forms, compact spacing and contained tables. The user-supplied colours and logo
take priority over generated palette and font recommendations.

The figure's 14 mPa threshold, 12.6 mPa result, disturbance contributions, ICC,
PC1 and candidate scores are demonstrations. They must never appear as live
results of functionality that has not been implemented. The present physics
model supports orbital shakers; advanced disturbance models, ICC, PDF ingestion
and biological surrogate optimization remain separate development work.
Screenshots must show real current outputs, the input assumptions and provenance
of samples. Never imply a model estimate or an author-provided statistic is
experimental validation of this application.
