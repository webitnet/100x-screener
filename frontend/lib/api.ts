const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/health`);
  return res.json();
}

export async function fetchModules() {
  const res = await fetch(`${API_BASE}/modules`);
  return res.json();
}

export async function runScan() {
  const res = await fetch(`${API_BASE}/scan`, { method: "POST" });
  return res.json();
}

export async function startAnalysis() {
  const res = await fetch(`${API_BASE}/analyse`, { method: "POST" });
  return res.json();
}

export async function getAnalysisStatus() {
  const res = await fetch(`${API_BASE}/analyse/status`);
  return res.json();
}

export async function getAnalysisResults() {
  const res = await fetch(`${API_BASE}/analyse/results`);
  return res.json();
}

export async function fetchProjects() {
  const res = await fetch(`${API_BASE}/projects`);
  return res.json();
}
