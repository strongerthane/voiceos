# Product

<!-- impeccable:product-schema 1 -->

## Platform

adaptive

## Users

Personal Windows users who want to operate their computer by voice while keeping a compact, always-available assistant out of the way.

## Product Purpose

VoiceOS listens to spoken requests, carries out supported desktop and web actions, and gives clear spoken and visual feedback without taking over the screen.

## Positioning

VoiceOS combines a top-screen, voice-first desktop surface with local microphone capture, deterministic actions, local Ollama routing, optional cloud AI, and confirmation before consequential actions.

## Operating Context

The assistant sits above other desktop applications. Its important states are idle, listening, thinking, executing, confirmation, completion, and recoverable error.

## Capabilities and Constraints

- Preserve voice commands, microphone capture, app and web actions, email drafts, Ollama support, existing TTS fallback, and the compact top-screen behavior.
- Consequential actions retain an explicit confirmation step.
- The surface must stay compact, keyboard-accessible, and readable over varied desktop backgrounds.
- Product truth inferred from the existing implementation and user requests; the visual system is being replaced.

## Brand Commitments

VoiceOS is a premium, voice-first personal assistant. The user supplied a minimal black voice bar with a cyan-to-violet waveform as a binding visual reference.

## Evidence on Hand

- Existing floating UI: `Backend/original/floating_ui.py`
- Voice pipeline: `Backend/original/voice_io.py`
- User-provided reference screenshots from this task.

## Product Principles

- Voice interaction is the primary interface.
- The assistant recedes until attention is needed.
- States should be legible without exposing implementation details.
- Motion must clarify listening and execution, not decorate a utility window.
