import { useState } from "react";
import { createJob, type CreateJobPayload } from "../api";

interface Props {
  onCreated: () => void;
}

export default function CreateJobForm({ onCreated }: Props) {
  const [prompt, setPrompt] = useState("");
  const [detailLevel, setDetailLevel] = useState<"low" | "medium" | "high">("medium");
  const [modelSource, setModelSource] = useState<"auto" | "local" | "remote">("local");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    const payload: CreateJobPayload = {
      prompt: prompt.trim(),
      mode: "3d_model",
      detail_level: detailLevel,
      model_source: modelSource,
    };
    try {
      await createJob(payload);
      setPrompt("");
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card" onSubmit={handleSubmit}>
      <h2>Create 3D model</h2>
      <label>
        Describe what to model
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="e.g. a desk lamp with a rotating shade, base 80mm diameter"
          rows={4}
          minLength={5}
          maxLength={2000}
          required
        />
      </label>
      <div className="row">
        <label>
          Detail level
          <select value={detailLevel} onChange={(e) => setDetailLevel(e.target.value as "low" | "medium" | "high")}>
            <option value="low">low</option>
            <option value="medium">medium</option>
            <option value="high">high</option>
          </select>
        </label>
        <label>
          Model source
          <select value={modelSource} onChange={(e) => setModelSource(e.target.value as "auto" | "local" | "remote")}>
            <option value="local">Local (Ollama) - fast</option>
            <option value="auto">Auto (Local first)</option>
            <option value="remote">Remote (OpenRouter) - slow</option>
          </select>
        </label>
      </div>
      {error && <div className="error">{error}</div>}
      <button className="primary" type="submit" disabled={busy || prompt.trim().length < 5}>
        {busy ? "Submitting…" : "Generate"}
      </button>
    </form>
  );
}
