"use client";

import { useEffect, useState } from "react";
import UploadCard from "@/components/UploadCard";
import ResultPanel from "@/components/ResultPanel";
import { createTryOn, health, listResults, subscribeToJob, type TryOnJob } from "@/lib/api";

export default function Home() {
  const [garment, setGarment] = useState<File | null>(null);
  const [person, setPerson] = useState<File | null>(null);
  const [description, setDescription] = useState("");
  const [job, setJob] = useState<TryOnJob | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [online, setOnline] = useState<boolean | null>(null);
  const [history, setHistory] = useState<TryOnJob[]>([]);

  useEffect(() => {
    health().then(setOnline);
    listResults().then((items) => setHistory(items.filter((j) => j.status === "done")));
  }, []);

  useEffect(() => {
    if (!job || job.status === "done" || job.status === "error") return;
    return subscribeToJob(job.id, setJob, (e) => setError(e.message));
  }, [job?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (job?.status === "done") setHistory((h) => [job, ...h.filter((x) => x.id !== job.id)]);
  }, [job]);

  const submit = async () => {
    if (!garment) return;
    setSubmitting(true);
    setError(null);
    try {
      setJob(await createTryOn(garment, person, description));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  const reset = () => {
    setJob(null);
    setError(null);
  };

  return (
    <main className="shell">
      <nav className="nav">
        <span className="brand">Atelier</span>
        <span className={`status-dot ${online === false ? "offline" : ""}`}>
          {online === null ? "Conectando" : online ? "Backend activo" : "Backend no disponible"}
        </span>
      </nav>

      {!job && (
        <>
          <section className="hero">
            <h1>Pruébatelo antes de comprarlo.</h1>
            <p>Sube la prenda. La IA la viste, Claude dirige la sesión y el refinado la lleva a nivel editorial.</p>
          </section>
          <div className="stack">
            <UploadCard title="Prenda" hint="Obligatorio" file={garment} onChange={setGarment} />
            <UploadCard title="Tu foto" hint="Opcional · cuerpo entero" file={person} onChange={setPerson} />
            <input
              className="field"
              placeholder="Describe la prenda (ej. vestido rojo satinado)"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
            {error && <div className="card error">{error}</div>}
            <button className="btn" disabled={!garment || submitting || online === false} onClick={submit}>
              {submitting ? "Enviando…" : "Generar look"}
            </button>
          </div>
        </>
      )}

      {job && <ResultPanel job={job} onReset={reset} />}

      {history.length > 0 && (
        <>
          <h2 className="section-title">Tus looks</h2>
          <div className="history">
            {history.slice(0, 9).map((h) => (
              <img key={h.id} src={h.final_image_url ?? ""} alt={h.description} onClick={() => setJob(h)} />
            ))}
          </div>
        </>
      )}
    </main>
  );
}
