# Design

## Source of truth
Active · 2026-10-25. Surfaces: overview, setup, live workspace, evidence and report. Evidence: user master build prompt, existing React pages, API schemas and screenshots. This contract governs the redesign.

## Brand
A precise industrial inspection instrument: calm, technical, transparent. Trust comes from image evidence, measured timings and explicit uncertainty. Avoid chatbot layouts, invented telemetry and unsupported accuracy claims.

## Product goals
Make an inspection understandable from acquisition through verification. Start a synthetic scenario, locate a candidate, inspect evidence and export the decision. Preserve upload, review and additional-capture workflows.

## Personas and jobs
Operators investigate regions and resolve reviews. Judges inspect autonomous decisions, reproducibility and actual OpenCV runtime. Developers trace tools without confusing synthetic results with production accuracy.

## Information architecture
Left navigation: overview and new inspection. Utility bar: current surface, local time, measured API health. Overview: primary action, visual latest-run preview, recorded metrics, searchable ledger, distribution and runtime. Workspace: run header, board viewer, agent/evidence/report tabs, candidate strip and budget.

## Design principles
Images carry the story. Spacious headings, legible instrument details. Separate runtime evidence from deployment claims. Every enabled action works. Uncertainty is a first-class outcome. Overlays appear only in their declared coordinate system.

## Visual language
Graphite #090d12; panel #10171f; border #25313d; cyan #67e8f9; restrained mint #8be9be; white #edf2f6; secondary #9baebd. Red defect, amber likely, violet review, mint cleared. Space Grotesk body/headings; JetBrains Mono measurements. 4px rhythm, 12px panels, restrained shadows, line icons, real PCB imagery. Short transitions, reduced motion support.

## Components
App shell owns navigation. Shared Icon, VerdictChip, StatusDot and ScoreBar; index.css owns tokens and panels. API records supply metrics, activity and latest preview. Viewer exposes fit, zoom and overlay controls.

## Accessibility
Target WCAG 2.2 AA: visible focus, semantic headings, labelled inputs, named icon buttons, status text alongside color. Candidate buttons outside canvas. Errors preserve recovery controls. Reduced-motion preference.

## Responsive behavior
Below 1100px compact sidebar; below 760px header navigation and stacked content. Workspace viewer has explicit useful height on mobile and document scrolling. Tables scroll within panel. Primary controls 44px.

## Interaction states
Initial loading, retryable offline errors, clear empty ledger, disabled start until required images supplied. Never label failed registration clean. Stream failures recover through polling. Review errors stay near controls. Report loading recovers when generation completes.

## Content voice
Measured: confirmed defect, additional capture required, synthetic scenario. Scores are heuristic. Distinguish original test, aligned test and independent view. Show actual activity and durations.

## Implementation constraints
React/TypeScript/Vite/Tailwind and local fonts; no new runtime dependencies. Browser-check overview, setup, inspection, evidence and report; build and lint. AWS stays unverified until actual execution.

## Open questions
- [ ] Real PCB evaluation and AWS execution remain submission work; owner: project team; affects compliance and accuracy claims.
