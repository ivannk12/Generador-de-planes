"use client";

import { useEffect, useMemo, useState } from "react";
import JsonEditor from "@/components/JsonEditor";
import {
  fetchCfgFromRow,
  fetchPdf,
  fetchPreview,
  fetchProgressPdf,
  fetchProgressPreview,
  fetchSampleCfg,
} from "@/lib/api";

function getFileName(contentDisposition: string | null, fallback: string) {
  if (!contentDisposition) return fallback;
  const match = contentDisposition.match(/filename="?([^";]+)"?/i);
  return match?.[1] || fallback;
}

async function downloadResponse(res: Response, fallbackName: string) {
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = getFileName(res.headers.get("content-disposition"), fallbackName);
  a.click();
  URL.revokeObjectURL(url);
}

export default function HomePage() {
  const [planType, setPlanType] = useState<1 | 2 | 3>(3);
  const [cfgText, setCfgText] = useState("{}");
  const [rowText, setRowText] = useState("");
  const [planPreviewHtml, setPlanPreviewHtml] = useState("");
  const [progressPreviewHtml, setProgressPreviewHtml] = useState("");
  const [previewMode, setPreviewMode] = useState<"plan" | "progress">("plan");
  const [status, setStatus] = useState("Cargando plantilla...");
  const [busy, setBusy] = useState(false);

  const cfgObject = useMemo(() => {
    try {
      return JSON.parse(cfgText);
    } catch {
      return null;
    }
  }, [cfgText]);

  async function loadSample(type: 1 | 2 | 3) {
    setBusy(true);
    setStatus(`Cargando configuración tipo ${type}...`);
    try {
      const payload = await fetchSampleCfg(type);
      setCfgText(JSON.stringify(payload.cfg, null, 2));
      setStatus("Plantilla cargada");
    } catch (err) {
      setStatus((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function handlePreviewPlan() {
    if (!cfgObject) {
      setStatus("JSON inválido");
      return;
    }

    setBusy(true);
    setStatus("Generando preview del Plan...");

    try {
      const payload = await fetchPreview(cfgObject);
      setPlanPreviewHtml(payload.html || "");
      setPreviewMode("plan");
      setStatus(`Preview del Plan generado (${payload.plan_model?.days?.length || 0} días)`);
    } catch (err) {
      setStatus((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function handlePreviewProgress() {
    if (!cfgObject) {
      setStatus("JSON inválido");
      return;
    }

    setBusy(true);
    setStatus("Generando preview del Registro...");
    try {
      const payload = await fetchProgressPreview(cfgObject);
      setProgressPreviewHtml(payload.html || "");
      setPreviewMode("progress");
      setStatus("Preview del Registro generado");
    } catch (err) {
      setStatus((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function handlePdf() {
    if (!cfgObject) {
      setStatus("JSON inválido");
      return;
    }

    setBusy(true);
    setStatus("Generando Plan...");

    try {
      const studentName = String((cfgObject as any)?.meta?.student_name || "Estudiante").trim() || "Estudiante";
      const planFallbackName = `Plan de Estudio ICFES ${studentName}.pdf`;
      const progressFallbackName = `Registro de Progreso ICFES ${studentName}.pdf`;

      const planRes = await fetchPdf(cfgObject);
      await downloadResponse(planRes, planFallbackName);

      setStatus("Generando Registro...");
      const progressRes = await fetchProgressPdf(cfgObject);
      await downloadResponse(progressRes, progressFallbackName);

      setStatus("Listo");
    } catch (err) {
      setStatus((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleImportRow() {
    if (!rowText.trim()) {
      setStatus("Pega una fila de Sheets antes de importar");
      return;
    }

    setBusy(true);
    setStatus("Importando fila...");
    try {
      const payload = await fetchCfgFromRow(planType, rowText);
      setCfgText(JSON.stringify(payload.cfg, null, 2));
      setStatus("Fila importada, listo para Preview/PDF");
    } catch (err) {
      setStatus((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    loadSample(3);
  }, []);

  return (
    <main className="page">
      <section className="toolbar">
        <h1>Preicfes Plan Studio</h1>
        <p>Frontend sin lógica de plan: backend genera preview, PDF del plan y Registro de Progreso.</p>

        <div className="row">
          <label htmlFor="planType">Tipo</label>
          <select
            id="planType"
            value={planType}
            onChange={(e) => {
              const nextType = Number(e.target.value) as 1 | 2 | 3;
              setPlanType(nextType);
              loadSample(nextType);
            }}
            disabled={busy}
          >
            <option value={1}>Tipo 1</option>
            <option value={2}>Tipo 2</option>
            <option value={3}>Tipo 3</option>
          </select>

          <button onClick={() => loadSample(planType)} disabled={busy}>Recargar plantilla</button>
          <button onClick={handlePreviewPlan} disabled={busy}>Preview Plan</button>
          <button onClick={handlePreviewProgress} disabled={busy}>Preview Registro</button>
          <button onClick={handlePdf} disabled={busy}>Generar PDFs</button>
        </div>

        <div className="rowImport">
          <label htmlFor="rowText">Pega aquí la fila del Sheets (1 fila)</label>
          <textarea
            id="rowText"
            className="rowTextArea"
            value={rowText}
            onChange={(e) => setRowText(e.target.value)}
            placeholder="Pega una fila completa copiada desde Google Sheets (separada por tabs)"
            spellCheck={false}
          />
          <button onClick={handleImportRow} disabled={busy}>Importar fila</button>
        </div>

        <div className="status">{status}</div>
      </section>

      <section className="workspace">
        <article className="panel editorPanel">
          <h2>cfg (JSON)</h2>
          <JsonEditor value={cfgText} onChange={setCfgText} />
        </article>

        <article className="panel previewPanel">
          <h2>Preview</h2>
          <div className="row">
            <button onClick={() => setPreviewMode("plan")} disabled={busy || !planPreviewHtml}>Ver Plan</button>
            <button onClick={() => setPreviewMode("progress")} disabled={busy || !progressPreviewHtml}>Ver Registro</button>
          </div>
          {previewMode === "plan" && planPreviewHtml ? (
            <iframe title="preview-plan" className="previewFrame" srcDoc={planPreviewHtml} />
          ) : previewMode === "progress" && progressPreviewHtml ? (
            <iframe title="preview-progress" className="previewFrame" srcDoc={progressPreviewHtml} />
          ) : (
            <div className="empty">
              {previewMode === "plan"
                ? "Genera el Preview Plan para ver el calendario"
                : "Genera el Preview Registro para ver el formato de progreso"}
            </div>
          )}
        </article>
      </section>
    </main>
  );
}
