# NaturalCAD Web App

Website/product frontend for the hosted NaturalCAD lane on `main`.

## Stack

- Next.js
- TypeScript
- Vercel target

## Routes

- `/` - landing page
- `/app` - prompt/generate/iterate/export workspace

## Environment

Copy `.env.example` to `.env.local` and fill in real values:

- `NEXT_PUBLIC_API_BASE_URL`
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`

## Phase 1 contract

Phase 1 is guest-first:
- `POST /session/guest`
- `POST /projects`
- `POST /projects/:id/generate`

Prompt harvesting is required from the beginning.
Heavy artifacts should not all be stored by default; STEP should be persisted on export request.

## Local run

```bash
npm install
npm --workspace @naturalcad/web run dev
```

## Build check

```bash
npm --workspace @naturalcad/web run typecheck
npm --workspace @naturalcad/web run build
```
