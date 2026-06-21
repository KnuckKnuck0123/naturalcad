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

Copy `.env.example` to `.env.local` and fill in server-only values:

- `NATURALCAD_BACKEND_URL`
- `NATURALCAD_API_KEY`

Neither value is exposed to the browser. The Next.js BFF stores the guest
session in an HttpOnly cookie and forwards authenticated requests to the API.

## Phase 1 contract

Phase 1 is guest-first and iterative:
- create a guest session and project
- upload up to three sanitized reference images
- start an asynchronous generation from any selected parent version
- answer clarification questions and poll until a version is complete

Prompt harvesting is required from the beginning.
Images guide generation but are not measurement-grade reconstruction. Guest
source images expire after seven days.

Schedule `POST /v1/internal/cleanup-attachments` with the gateway key at least
daily. The endpoint is idempotent and removes expired quarantine and sanitized
objects.

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
