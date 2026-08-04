import { useCallback, useEffect, useRef, useState } from "react";
import { ACTIVE_STATUSES, listJobs, me, setToken, type Job } from "./api";
import AuthPage from "./components/AuthPage";
import CreateJobForm from "./components/CreateJobForm";
import JobList from "./components/JobList";

export default function App() {
  const [email, setEmail] = useState<string | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const started = useRef(false);

  const refresh = useCallback(async () => {
    try {
      setJobs(await listJobs());
      setLoadError(null);
    } catch {
      /* transient errors are fine; next poll will retry */
    }
  }, []);

  const loadMe = useCallback(async (): Promise<boolean> => {
    if (!localStorage.getItem("gvs_access_token")) return false;
    try {
      const u = await me();
      setEmail(u.email);
      void refresh();
      return true;
    } catch {
      setToken(null);
      return false;
    }
  }, [refresh]);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void loadMe().finally(() => setLoading(false));
  }, [loadMe]);

  useEffect(() => {
    if (!email) return;
    void refresh();
    const hasActive = () => jobs.some((j) => ACTIVE_STATUSES.includes(j.status));
    const interval = setInterval(() => {
      void refresh();
      if (!hasActive()) clearInterval(interval);
    }, 2000);
    return () => clearInterval(interval);
  }, [email, refresh, jobs]);

  function handleLogout() {
    setToken(null);
    setEmail(null);
    setJobs([]);
  }

  if (loading) {
    return (
      <div className="app">
        <p className="muted">Loading…</p>
      </div>
    );
  }

  if (!email) {
    return (
      <AuthPage
        onAuthed={(token) => {
          setToken(token);
          void loadMe();
        }}
      />
    );
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">Gemini Vision Studio</div>
        <div className="topbar-right">
          <span className="muted small">{email}</span>
          <button className="btn" onClick={handleLogout}>
            Log out
          </button>
        </div>
      </header>

      <main>
        <CreateJobForm onCreated={() => void refresh()} />
        {loadError && <div className="error">{loadError}</div>}
        <h2>Jobs</h2>
        <JobList jobs={jobs} onChanged={() => void refresh()} />
      </main>
    </div>
  );
}
