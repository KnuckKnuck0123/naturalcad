# NaturalCAD GitHub Push Safety Plan

## Goal
Keep iteration fast while preventing secret leakage and noisy runtime artifacts from being pushed.

## Branch strategy
- `main` stays deployable.
- Do work in short-lived branches: `feat/*`, `fix/*`, `chore/*`, `sec/*`.
- Open PRs for any change touching security/auth/secrets/runtime infra.

## Required pre-push checks
Run before every push:

```bash
./scripts/prepush-check.sh
```

What it blocks:
- tracked `.env` files
- tracked runtime logs (`artifacts/logs/*.jsonl`)
- tracked virtualenv content
- staged diff lines that look like tokens/secrets

## Secrets policy
- Never commit credentials to repo files.
- Keep runtime secrets in platform secret stores only:
  - Hugging Face Space secrets (`NATURALCAD_API_KEY`)
  - Modal secrets (`OPENROUTER_API_KEY`, `NATURALCAD_API_KEY`, Supabase keys)
- If a key is exposed, rotate immediately and force-push removal only after rotation.

## Commit hygiene
- Keep commits scoped (one concern per commit).
- Avoid mixing docs + infra + security changes in one commit when possible.
- Use clear commit tags:
  - `sec:` for security hardening
  - `infra:` for deployment/runtime wiring
  - `docs:` for docs only

## PR checklist
- [ ] No secrets or tokens in diff
- [ ] No `.env` or runtime logs tracked
- [ ] `.gitignore` still protects artifacts/logs
- [ ] Local smoke test completed (at least one prompt)
- [ ] If security-related, include threat + mitigation note in PR description

## Release cadence
- Batch low-risk docs/UI changes.
- Ship security and infra fixes quickly in small PRs.
- Tag stable checkpoints for team testing (example: `alpha-2026-04-18-1`).
