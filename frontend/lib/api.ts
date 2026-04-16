const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export async function fetchSampleCfg(planType: number) {
  const res = await fetch(`${API_BASE}/api/plan/sample/${planType}`, { cache: "no-store" });

  if (!res.ok) throw new Error(`No se pudo cargar sample tipo ${planType}`);
  return res.json();
}

export async function fetchPreview(cfg: unknown) {
  const res = await fetch(`${API_BASE}/api/plan/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cfg }),
  });

  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new Error(payload.detail || "Error en preview");
  }
  return res.json();
}

export async function fetchProgressPreview(cfg: unknown) {
  const res = await fetch(`${API_BASE}/api/plan/progress/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cfg }),
  });

  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new Error(payload.detail || "Error en preview del Registro de Progreso");
  }
  return res.json();
}

export async function fetchPdf(cfg: unknown) {
  const res = await fetch(`${API_BASE}/api/plan/pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cfg }),
  });

  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new Error(payload.detail || "Error al generar PDF");
  }
  return res;
}

export async function fetchProgressPdf(cfg: unknown) {
  const res = await fetch(`${API_BASE}/api/plan/progress/pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cfg }),
  });

  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new Error(payload.detail || "Error al generar Registro de Progreso");
  }
  return res;
}

export async function fetchCfgFromRow(planType: number, rowText: string) {
  const res = await fetch(`${API_BASE}/api/plan/from_row`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ plan_type: planType, row_text: rowText }),
  });

  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new Error(payload.detail || "Error al importar fila");
  }
  return res.json();
}
