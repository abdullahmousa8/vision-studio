import { lazy, Suspense, useState } from "react";
import { cancelJob, deleteJob, type Job } from "../api";

const ModelViewer = lazy(() => import("./ModelViewer"));

const STATUS_LABEL: Record<string, string> = {
  pending: "Queued",
  decomposing: "Decomposing",
  generating: "Generating parts",
  validating: "Validating",
  assembling: "Assembling",
  exporting: "Exporting",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
};

function StatusPill({ status }: { status: Job["status"] }) {
  return <span className={`pill ${status}`}>{STATUS_LABEL[status] ?? status}</span>;
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const s = Math.max(0, Math.floor(diff / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  return `${Math.floor(m / 60)}h ago`;
}

function JobCard({ job, onCancelled, onView }: { job: Job; onCancelled: () => void; onView?: () => void }) {  const active = ["pending", "decomposing", "generating", "validating", "assembling", "exporting"].includes(job.status);

  return (
    <li className={`card job ${job.status}`}>
      <div className="job-head">
        <span className="job-id" title={job.job_id}>
          {job.job_id.slice(0, 8)}
        </span>
        <StatusPill status={job.status} />
        <span className="muted small">{timeAgo(job.created_at)}</span>
      </div>

      {active && (
        <div className="progress">
          <div className="progress-bar" style={{ width: `${Math.max(2, job.progress)}%` }} />
        </div>
      )}
      {!active && <div className="progress-track" />}

      <div className="job-meta">
        <span>
          {job.progress}% · est ${job.cost_estimate_usd.toFixed(3)} · actual ${job.cost_actual_usd.toFixed(3)}
        </span>
      </div>

      {job.error_message && <div className="error">{job.error_message}</div>}

      <div className="job-actions">
        {job.preview_url && (
          <a className="btn" href={job.preview_url} target="_blank" rel="noreferrer">
            Preview
          </a>
        )}
        {job.result_url && (
          <>
            <button className="btn primary" onClick={onView}>
              View 3D
            </button>
            <a className="btn" href={job.result_url} target="_blank" rel="noreferrer">
              Download STL
            </a>
          </>
        )}
        {active && (
          <button
            className="btn danger"
            onClick={async () => {
              await cancelJob(job.job_id);
              onCancelled();
            }}
          >
            Cancel
          </button>
        )}
        <button
          className="btn danger"
          title="Remove this job"
          onClick={async () => {
            if (!window.confirm("Delete this job and its files?")) return;
            await deleteJob(job.job_id);
            onCancelled();
          }}
        >
          Delete
        </button>
      </div>
    </li>
  );
}

export default function JobList({ jobs, onChanged }: { jobs: Job[]; onChanged: () => void }) {
  const [viewing, setViewing] = useState<Job | null>(null);

  if (jobs.length === 0) {
    return <p className="muted">No jobs yet. Describe a model above to get started.</p>;
  }
  return (
    <>
      <ul className="job-list">
        {jobs.map((job) => (
          <JobCard key={job.job_id} job={job} onCancelled={onChanged} onView={() => setViewing(job)} />
        ))}
      </ul>

      {viewing?.result_url && (
        <div className="modal-backdrop" onClick={() => setViewing(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <span className="job-id">Model {viewing.job_id.slice(0, 8)}</span>
              <a className="btn" href={viewing.result_url} target="_blank" rel="noreferrer">
                Download STL
              </a>
              <button className="btn" onClick={() => setViewing(null)}>
                Close
              </button>
            </div>
            <Suspense fallback={<div className="viewer-overlay">Loading 3D viewer…</div>}>
              <ModelViewer jobId={viewing.job_id} />
            </Suspense>
          </div>
        </div>
      )}
    </>
  );
}
