"use client";

import { useEffect, useState } from "react";

interface Props {
  title: string;
  hint: string;
  file: File | null;
  onChange: (file: File | null) => void;
}

export default function UploadCard({ title, hint, file, onChange }: Props) {
  const [preview, setPreview] = useState<string | null>(null);

  useEffect(() => {
    if (!file) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  return (
    <label className="card drop">
      <input
        type="file"
        accept="image/jpeg,image/png,image/webp,image/heic"
        onChange={(e) => onChange(e.target.files?.[0] ?? null)}
      />
      <div className="drop-frame">
        {preview ? <img src={preview} alt={title} /> : <span>Toca para elegir una foto</span>}
      </div>
      <div className="drop-meta">
        <strong>{title}</strong>
        <span>{hint}</span>
      </div>
    </label>
  );
}
