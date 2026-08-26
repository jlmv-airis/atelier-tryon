export type JobStatus = "queued" | "processing" | "done" | "error";
export type JobStage = "queued" | "tryon" | "claude" | "refine" | "done" | "error";

export interface TryOnJob {
  id: string;
  user_id: string;
  status: JobStatus;
  stage: JobStage;
  description: string;
  garment_url: string | null;
  person_url: string | null;
  base_image_url: string | null;
  improved_prompt: string | null;
  final_image_url: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export function getUserId(): string {
  if (typeof window === "undefined") return "anonymous";
  const key = "tryon_user_id";
  let id = window.localStorage.getItem(key);
  if (!id) {
    id = crypto.randomUUID();
    window.localStorage.setItem(key, id);
  }
  return id;
}

async function parseError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    return typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
  } catch {
    return `HTTP ${res.status}`;
  }
}

export async function createTryOn(garment: File, person: File | null, description: string): Promise<TryOnJob> {
  const form = new FormData();
  form.append("image", garment, garment.name || "garment.jpg");
  if (person) form.append("person", person, person.name || "person.jpg");
  form.append("description", description);
  form.append("user_id", getUserId());
  const res = await fetch(`${API_URL}/tryon`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function getTryOn(jobId: string): Promise<TryOnJob> {
  const res = await fetch(`${API_URL}/tryon/${jobId}`, { cache: "no-store" });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function listResults(): Promise<TryOnJob[]> {
  const res = await fetch(`${API_URL}/results?user_id=${encodeURIComponent(getUserId())}`, { cache: "no-store" });
  if (!res.ok) return [];
  return (await res.json()).items;
}

export async function health(): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}/health`, { cache: "no-store" });
    return res.ok;
  } catch {
    return false;
  }
}

export function subscribeToJob(jobId: string, onUpdate: (job: TryOnJob) => void, onError: (e: Error) => void): () => void {
  let stopped = false;
  const source = typeof EventSource !== "undefined" ? new EventSource(`${API_URL}/tryon/${jobId}/events`) : null;

  const poll = async () => {
    while (!stopped) {
      try {
        const job = await getTryOn(jobId);
        onUpdate(job);
        if (job.status === "done" || job.status === "error") return;
      } catch (e) {
        onError(e as Error);
        return;
      }
      await new Promise((r) => setTimeout(r, 2500));
    }
  };

  if (source) {
    source.onmessage = (ev) => {
      const job: TryOnJob = JSON.parse(ev.data);
      onUpdate(job);
      if (job.status === "done" || job.status === "error") source.close();
    };
    source.onerror = () => {
      source.close();
      if (!stopped) poll();
    };
  } else {
    poll();
  }

  return () => {
    stopped = true;
    source?.close();
  };
}
