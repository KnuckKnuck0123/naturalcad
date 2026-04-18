# NaturalCAD Startup / Shutdown Playbook

## Scope
Operational runbook for local testing and hosted testing (HF Space + Modal worker).

---

## A) Local startup (recommended)

### 1) Start/verify Modal worker
```bash
cd "apps/cad-worker"
modal deploy main.py
```
Copy endpoint URL (example):
`https://<user>--naturalcad-generate-cad-endpoint.modal.run`

### 2) Run local UI against Modal backend
From repo root:
```bash
export NATURALCAD_BACKEND_URL="https://<user>--naturalcad-generate-cad-endpoint.modal.run"
export NATURALCAD_API_KEY="<same value as NATURALCAD_API_KEY secret>"
npm run frontend:local
```
Open: `http://127.0.0.1:7860`

### 3) Optional local backend contract test
```bash
npm run backend:local
```
Note: this currently falls back to `archive/gradio-demo-backend-legacy`.

---

## B) Hugging Face startup (team/client staging)

Space settings:
- Variable: `NATURALCAD_BACKEND_URL`
- Secret: `NATURALCAD_API_KEY`

Worker-side required secrets:
- `OPENROUTER_API_KEY`
- `NATURALCAD_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_BUCKET`

Then restart/rebuild Space.

---

## C) Shutdown

### Local UI
- Stop process with `Ctrl+C` in terminal that ran `npm run frontend:local`.

### Local backend (if started)
- Stop process with `Ctrl+C` in terminal that ran `npm run backend:local`.

### Modal worker
- No manual shutdown required after deploy; Modal scales with traffic.
- If needed, stop app in Modal dashboard/CLI (`modal app stop <app-id>`).

---

## D) Quick troubleshooting

1. **`LLM provider unavailable (402)`**
   - OpenRouter credits missing or wrong API key/account.

2. **`Unauthorized` from backend**
   - `NATURALCAD_API_KEY` mismatch between caller and worker secret.

3. **HF push rejected due to binaries**
   - HF git policy may reject binary assets; use HF-safe deploy snapshot.

4. **No preview**
   - Verify STL exists; UI can generate GLB from STL when backend GLB storage is disabled.

---

## E) Safe pre-push check
Before pushing changes:
```bash
./scripts/prepush-check.sh
```
