# NaturalCAD Sprint Plan — Domain App V1

Status: active draft
Date: 2026-04-23

## Goal
Ship a domain-based NaturalCAD app that beats CADAM on core value:
- Better CAD outputs (including STEP)
- Conversational iteration
- Parametric sliders
- Model switching (OpenRouter)
- Usable without sign-in (strict guest limits)

## Product Positioning (v1)
1. Keep STEP export as a primary differentiator.
2. Match competitor UX where it matters: iteration chat + image upload + sliders.
3. Convert guests with strict free usage and account upgrades.

## Target Architecture (v1)
- `app.<domain>`: frontend web app (recommended: Vercel)
- `api.<domain>`: control-plane API (auth/session/project/job orchestration)
- Modal: CAD execution worker tier
- Supabase: auth, Postgres, storage, usage ledger
- Cloudflare: DNS, TLS, WAF, bot/rate rules
- OpenRouter: model routing (fast/balanced/quality)

## Feature Scope (must-have)
### 1) Conversational CAD
- Project/thread with versioned outputs
- Follow-up prompts refine previous version
- Version history + rollback/select

### 2) Parametric Sliders
- Extract/edit safe numeric parameters from generated model spec
- Rebuild quickly from params without full regeneration when possible

### 3) Model Switcher
- User-selectable quality mode: `Fast`, `Balanced`, `Quality`
- Backend maps each mode to selected OpenRouter model + token/time caps

### 4) Guest + Account Auth
- Guest usage without sign-in
- Strict guest quotas and lower complexity limits
- Email/password signup + magic link (Google optional later)

## Ownership Split

### Leeroy (me)
1. Write API contract for one-shot + conversational generation.
2. Design DB schema + migrations for projects/versions/jobs/usage.
3. Define quota and spend guardrail policy (guest vs signed-in tiers).
4. Create implementation ticket sequence for backend + frontend.
5. Draft domain cutover DNS record checklist once domain/provider are known.

### Noah
1. Confirm domain + DNS provider (Cloudflare setup in progress).
2. Choose hosting targets:
   - frontend: Vercel (recommended) or Cloudflare Pages
   - API: Vercel serverless or Cloudflare Workers
3. Confirm launch auth mode:
   - email/password + magic link (recommended)
   - Google optional now/later
4. Confirm initial quota policy targets (runs/day for guest and signed-in).

## Proposed 10-Day Build Order

## Day 1-2: Control Plane Foundation
- API scaffold (`api.<domain>`)
- Supabase schema + migrations
- Request auth/session middleware (guest + signed-in)

## Day 3-4: Conversational CAD v1
- Create project/thread/version endpoints
- Hook generation pipeline to version graph
- Add history/rollback support

## Day 5: Model Switcher
- Add mode selector API + frontend wiring
- Map `Fast/Balanced/Quality` to OpenRouter model configs

## Day 6-7: Parametric Sliders v1
- Parameter extraction on successful generation
- Slider panel + parameter patch endpoint
- Fast regenerate path from param changes

## Day 8: Quotas + Spend Guardrails
- Guest limits, signed-in limits, queue caps, timeout policy
- Spend alarm + soft kill switch behavior

## Day 9: Image Upload (guided generation)
- Upload handling + reference attachment flow
- Safety and size limits

## Day 10: Polish + Launch Prep
- UX cleanup, errors, empty states, queue messaging
- Domain cutover checklist execution

## Non-negotiable Guardrails
- Hard max prompt size and token caps by mode
- Queue depth limits + clean busy responses
- Per-user and per-IP rate limits
- Request timeout + cancellation
- Usage logging per job (model, tokens if available, latency, outcome)

## Branch Safety (do not break alpha)
- `main` = domain app development
- `huggingface` = alpha demo stability
- No feature migrations from `main` to `huggingface` unless explicitly marked alpha-safe
- `huggingface` only receives bugfixes/hotfixes needed to keep the public alpha stable

## Success Criteria (v1)
- User can generate one-shot CAD and export STEP.
- User can continue conversation to refine prior versions.
- User can tweak at least 4 common slider params on supported outputs.
- User can use app as guest (strict limits) and create account without Google.
- App remains stable under moderate concurrent traffic without runaway spend.
