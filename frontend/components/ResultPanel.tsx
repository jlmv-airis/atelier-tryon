"use client";

import { useState } from "react";
import type { TryOnJob } from "@/lib/api";

const STAGES: { key: TryOnJob["stage"]; label: string }[] = [
  { key: "tryon", label: "Try-on con IA" },
  { key: "claude", label: "Análisis editorial (Claude)" },
  { key: "refine", label: "Refinado hiperrealista" },
];

function stageIndex(stage: TryOnJob["stage"]): number {
  const i = STAGES.findIndex((s) => s.key === stage);
  return i === -1 ? (stage === "done" ? STAGES.length : 0) : i;
}

export default function ResultPanel({ job, onReset }: { job: TryOnJob; onReset: () => void }) {
  const [view, setView] = useState<"final" | "base">("final");

  if (job.status === "error") {
    return (
      <div className="card">
        <div className="error">No se pudo generar el look. {job.error}</div>
        <div style={{ padding: "0 18px 18px" }}>
          <button className="btn ghost" onClick={onReset}>Intentar de nuevo</button>
        </div>
      </div>
    );
  }

  if (job.status !== "done") {
    const current = stageIndex(job.stage);
    return (
      <div className="card progress">
        <h3>Creando tu look</h3>
        <p>{STAGES[current]?.label ?? "En cola"}. Suele tardar 1–3 minutos.</p>
        <div className="steps">
          {STAGES.map((s, i) => (
            <i key={s.key} className={i < current ? "on" : i === current ? "active" : ""} />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="result-frame">
        <img src={job.final_image_url ?? ""} alt="Resultado final" className={view === "final" ? "" : "hidden"} />
        <img src={job.base_image_url ?? ""} alt="Imagen base" className={view === "base" ? "" : "hidden"} />
        <span className="badge">{view === "final" ? "Editorial" : "Base"}</span>
      </div>
      <div className="segment">
        <button className={view === "final" ? "on" : ""} onClick={() => setView("final")}>Refinada</button>
        <button className={view === "base" ? "on" : ""} onClick={() => setView("base")}>Base</button>
      </div>
      {job.improved_prompt && (
        <div className="prompt">
          <strong>Dirección de arte (Claude)</strong>
          {job.improved_prompt}
        </div>
      )}
      <div style={{ padding: "0 18px 18px", display: "flex", gap: 10 }}>
        <a className="btn ghost" style={{ textAlign: "center", textDecoration: "none" }}
           href={job.final_image_url ?? "#"} target="_blank" rel="noreferrer">Abrir</a>
        <button className="btn" onClick={onReset}>Nuevo look</button>
      </div>
    </div>
  );
}
