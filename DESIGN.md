# VoiceOS Design System

<!-- impeccable:design-schema 1 -->

## Visual World

Studio Voice Aperture: a compact translucent black notch integrated into the desktop's top edge. Compared directly with the official VoiceOS demonstration at https://www.voiceos.com/ on 2026-10-16, following the user's request to bring the implementation closer to that product. The moving prismatic voice field is the principal expressive color.

## Material and Palette

- Surface: neutral transparent black, presented with Windows per-pixel alpha. The bar uses 71% opacity and the confirmation sheet 82%; text stays opaque for readability. Outside the surfaces every pixel is fully transparent. No desktop screenshot or background plate is used by the live UI.
- Expression: cyan, electric blue, violet, and magenta only inside the living waveform and its reflections.
- Structure: soft asymmetric optical edges, flat controls, no title bars, utility strips, or embossed chrome.
- Depth: diffuse material illumination, native translucency, and a restrained spectral reflection at the lower edge. No inset bevels or drawn diagonal reflection lines.

## Typography

Use Segoe UI with compact, high-contrast labels. State language is short, literal, and secondary to the waveform.

## Component Character

- Idle: a 236px-wide notch with a 28px visible shell, one status light and a subdued micro-wave. No permanent wordmark or detached panel.
- Active: a 340px-wide notch with a 40px visible shell, centered against the top edge at y=0. Cyan, blue, violet, and magenta ribbons stay in the same header throughout the task.
- Working: the same notch unfolds to 380px wide and 92px high to show the current request while it is processed.
- Confirmation: the same 380px-wide notch unfolds vertically to contain recipient, subject, body preview, a flat light approval control, and quiet cancellation. It is one continuous material, without a second card or connector.
- Text input: hidden until explicitly requested with Ctrl+T.

## Motion

The waveform is the signature motion. Gaussian light volumes and bright contours overlap in a continuous fluid motion. Smoothed microphone levels control amplitude; the idle signal is subdued. The static glass and text are cached while the small light field updates around 30fps. All size changes use a brief, eased expansion from the same anchor point.

## Avoid

Traditional desktop framing, floating branded toolbar layouts, detached confirmation dialogs, metallic double outlines, beveled controls, embossed pill buttons, ornamental connectors, Gmail-inspired cards, status dashboards, and colored rails around the shell.
