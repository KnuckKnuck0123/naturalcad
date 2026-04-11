# NaturalCAD Prompt Handling MVP

## Goal

Handle weird public prompts without crashing, exposing code execution paths, or producing completely broken outputs.

## MVP rules

- Treat public input as prompt text, not code
- If the input looks like code or shell instructions, do not execute it as such
- If the prompt is underspecified, fall back to a conservative simple geometry
- If the prompt is malformed, keep the app responsive and log the failure
- Prefer boring safe fallback over clever brittle behavior

## Current guardrail behavior

### Suspicious input
Inputs containing code-like or hostile patterns such as:
- code fences
- `import`
- `exec`
- `eval`
- `subprocess`
- shell snippets like `curl`, `wget`, `rm -rf`

are treated as suspicious and mapped to a safe fallback prompt.

### Underspecified input
Very short or vague prompts fall back to a simple conservative geometry family with default dimensions.

## Why this matters

For public testing, the worst outcome is not an imperfect model. The worst outcome is a broken or abusable app.

NaturalCAD should prefer:
- graceful degradation
- clear logs
- safe defaults
- predictable outputs
