# Preicfes Plan Studio (MVP Web)

Migración de generador ICFES de Word/Colab a arquitectura web:
- `backend/`: FastAPI + lógica Tipo 1/2/3 + render HTML + exportación PDF con Playwright.
- `frontend/`: Next.js App Router para editar `cfg`, ver preview y descargar PDF.

## Arquitectura

- El frontend **no calcula reglas del plan**.
- Toda la lógica vive en backend (`backend/app/plan_engine.py`).
- Flujo:
  1. Frontend envía `cfg`.
  2. Backend valida y genera `PlanModel`.
  3. Backend renderiza HTML (`backend/app/templates/plan.html`).
  4. Para PDF, backend convierte HTML -> PDF con Playwright.

## Endpoints backend

- `GET /health`
- `GET /api/plan/sample/{plan_type}`
- `POST /api/plan/preview` body: `{ "cfg": { ... } }`
- `POST /api/plan/pdf` body: `{ "cfg": { ... } }` (descarga PDF)
- `POST /api/plan/progress/preview` body: `{ "cfg": { ... } }`
- `POST /api/plan/progress/pdf` body: `{ "cfg": { ... } }` (descarga Registro de Progreso en PDF)

## Backend setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
uvicorn app.main:app --reload --port 8000
```

## Frontend setup

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

Abrir: `http://localhost:3000`

## Variables de entorno frontend

`frontend/.env.local.example`:

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

## Integración futura con n8n

Puedes usar directamente `POST /api/plan/preview`, `POST /api/plan/progress/preview`, `POST /api/plan/pdf` y `POST /api/plan/progress/pdf` enviando `cfg` como JSON.

## Descarga en frontend

El botón `Generar PDF` ahora ejecuta dos descargas consecutivas con el mismo `cfg`:
1. Plan de estudio (`/api/plan/pdf`)
2. Registro de progreso (`/api/plan/progress/pdf`)
