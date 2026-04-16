#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

echo "📁 Root: $ROOT_DIR"
echo "🚀 Iniciando backend + frontend..."

# --- BACKEND ---
if [ ! -d "$BACKEND_DIR" ]; then
  echo "❌ No existe carpeta backend en: $BACKEND_DIR"
  exit 1
fi

cd "$BACKEND_DIR"

# Crear venv si no existe
if [ ! -d ".venv" ]; then
  echo "🐍 Creando venv en backend/.venv..."
  python3 -m venv .venv
fi

# Activar venv
source .venv/bin/activate

# Instalar deps si falta requirements.txt
if [ ! -f "requirements.txt" ]; then
  echo "❌ Falta backend/requirements.txt"
  exit 1
fi

echo "📦 Instalando dependencias backend..."
pip install -r requirements.txt

# Instalar Chromium para Playwright (opcional)
if [ "${SKIP_PLAYWRIGHT_INSTALL:-0}" = "1" ]; then
  echo "⏭️  Saltando instalación de Chromium (SKIP_PLAYWRIGHT_INSTALL=1)"
else
  echo "🧩 Instalando Chromium (Playwright)..."
  python -m playwright install chromium || true
fi

BACK_PID=""
if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  if curl --max-time 5 -sS http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "♻️  Ya hay un backend sano en :8000. Se reutilizará."
  else
    echo "❌ El puerto 8000 ya está ocupado por otro proceso y no responde a /health."
    exit 1
  fi
else
  echo "✅ Backend listo. Lanzando Uvicorn en :8000 ..."
  # En algunas instalaciones de macOS/paths sincronizados (iCloud),
  # watchfiles puede fallar con "Operation not permitted". Se ejecuta sin --reload.
  uvicorn app.main:app --port 8000 > "$ROOT_DIR/backend.log" 2>&1 &
  BACK_PID=$!
  echo "🧠 Backend PID: $BACK_PID"
fi

# --- FRONTEND ---
cd "$FRONTEND_DIR"

if [ ! -f "package.json" ]; then
  echo "❌ Falta frontend/package.json"
  exit 1
fi

# Cargar nvm dentro del script para evitar que bash use un Node global distinto.
if [ -s "$HOME/.nvm/nvm.sh" ]; then
  export NVM_DIR="$HOME/.nvm"
  # shellcheck disable=SC1090
  . "$NVM_DIR/nvm.sh"
  if [ -f "$ROOT_DIR/.nvmrc" ]; then
    nvm use >/dev/null 2>&1 || nvm install >/dev/null 2>&1
  fi
fi

if command -v node >/dev/null 2>&1; then
  NODE_MAJOR="$(node -p "process.versions.node.split('.')[0]")"
  echo "🟢 Usando Node $(node -v)"
  if [ "$NODE_MAJOR" -ge 24 ]; then
    echo "❌ Detectado Node $(node -v). Este proyecto debe correr con Node 20 o 22 LTS."
    echo "❌ Con Node 24 el frontend puede quedarse colgado y no abrir http://127.0.0.1:3000."
    echo "➡️  Cambia a Node 20/22 y vuelve a correr: bash start.sh"
    exit 1
  fi
fi

# Crear .env.local desde .env.local.example si no existe
if [ -f ".env.local.example" ] && [ ! -f ".env.local" ]; then
  echo "🧪 Creando frontend/.env.local..."
  cp .env.local.example .env.local
fi

echo "📦 Instalando dependencias frontend..."
npm install

if lsof -nP -iTCP:3000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "❌ El puerto 3000 ya está ocupado. Cierra ese proceso y vuelve a correr bash start.sh."
  exit 1
fi

echo "✅ Frontend listo. Lanzando Next.js en http://127.0.0.1:3000 ..."
PREWARM_PID=""

cleanup() {
  echo "🧹 Cerrando frontend + backend..."
  if [ -n "$PREWARM_PID" ]; then
    kill $PREWARM_PID 2>/dev/null || true
  fi
  if [ -n "$BACK_PID" ]; then
    kill $BACK_PID 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

prewarm_frontend() {
  echo "🔥 Precalentando la primera carga del frontend en segundo plano..."

  for _ in $(seq 1 120); do
    if lsof -nP -iTCP:3000 -sTCP:LISTEN >/dev/null 2>&1; then
      if curl --max-time 120 -sS http://127.0.0.1:3000 >/dev/null; then
        echo "✅ App lista en http://127.0.0.1:3000"
      else
        echo "⚠️  Next.js abrió el puerto 3000, pero la primera carga no terminó a tiempo."
      fi
      return 0
    fi

    sleep 1
  done

  echo "⚠️  Next.js tardó demasiado en abrir el puerto 3000."
}

prewarm_frontend &
PREWARM_PID=$!

echo "💡 Deja esta terminal abierta. La primera compilación puede tardar un poco."
npm run dev
