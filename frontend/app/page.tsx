"use client";

import { useEffect, useState, useRef, useCallback, useMemo } from "react";
import {
  fetchHealth,
  runScan,
  startAnalysis,
  getAnalysisStatus,
  getAnalysisResults,
  fetchAlerts,
} from "@/lib/api";
import ProjectCard from "@/components/ProjectCard";
import ModuleStatus from "@/components/ModuleStatus";
import AlertFeed from "@/components/AlertFeed";
import type { AlertItem } from "@/components/AlertFeed";
import type { AnalysisData } from "@/components/ProjectCard";

interface ProjectData {
  id?: string;
  name: string;
  ticker: string;
  price?: number | null;
  market_cap?: number | null;
  volume_24h?: number | null;
  volume_to_mcap_ratio?: number | null;
  age_days?: number | null;
  price_change_24h?: number | null;
  image?: string | null;
}

interface ScanResult {
  total_modules: number;
  successful: number;
  failed: number;
  warnings: number;
  failed_modules: { name: string; message: string }[];
  projects: ProjectData[];
  saved_to_db?: number;
  from_cache?: boolean;
}

interface AnalysisStatus {
  running: boolean;
  total: number;
  completed: number;
  analysed: number;
  failed: number;
  current_project: string;
}

interface AnalysisResultEntry {
  coingecko_id: string;
  total_score: number | null;
  tokenomics_score: number | null;
  github_score: number | null;
  onchain_score: number | null;
  audit_score: number | null;
  holder_score: number | null;
  smart_money_score: number | null;
  narrative_score: number | null;
  penalty_score: number | null;
  risk_level: string | null;
  red_flags: string[];
  tokenomics_data: Record<string, unknown> | null;
  github_data: Record<string, unknown> | null;
  onchain_data: Record<string, unknown> | null;
  audit_data: Record<string, unknown> | null;
  holder_data: Record<string, unknown> | null;
  whale_data: Record<string, unknown> | null;
  narrative_data: Record<string, unknown> | null;
  red_flag_data: Record<string, unknown> | null;
  social_score: number | null;
  exchange_score: number | null;
  social_data: Record<string, unknown> | null;
  exchange_data: Record<string, unknown> | null;
}

type SortOption = "score_desc" | "score_asc" | "mcap_asc" | "mcap_desc" | "volume_desc" | "change_desc" | "red_flags" | "name_asc";

const SORT_OPTIONS: { value: SortOption; label: string }[] = [
  { value: "score_desc", label: "Score (high to low)" },
  { value: "score_asc", label: "Score (low to high)" },
  { value: "mcap_asc", label: "MCap (low to high)" },
  { value: "mcap_desc", label: "MCap (high to low)" },
  { value: "volume_desc", label: "Volume 24h (high to low)" },
  { value: "change_desc", label: "24h Change (high to low)" },
  { value: "red_flags", label: "Red Flags (most first)" },
  { value: "name_asc", label: "Name (A-Z)" },
];

type FilterOption = "all" | "analysed" | "high_score" | "no_red_flags";

const FILTER_OPTIONS: { value: FilterOption; label: string }[] = [
  { value: "all", label: "All" },
  { value: "analysed", label: "Analysed only" },
  { value: "high_score", label: "Score 40+" },
  { value: "no_red_flags", label: "No Red Flags" },
];

function getTotalScore(analysis: AnalysisData | null): number {
  if (!analysis) return 0;
  let total = 0;
  const scoreKeys: [string, string][] = [
    ["tokenomics_analyzer", "tokenomics_score"],
    ["github_analyzer", "github_score"],
    ["onchain_analyzer", "onchain_score"],
    ["contract_auditor", "audit_score"],
    ["holder_analyzer", "holder_score"],
    ["whale_detector", "smart_money_score"],
    ["narrative_analyzer", "narrative_score"],
    ["social_tracker", "social_score"],
    ["exchange_tracker", "exchange_score"],
  ];
  for (const [modKey, scoreKey] of scoreKeys) {
    const val = analysis[modKey]?.[scoreKey] as number | undefined;
    if (val != null) total += val;
  }
  const penalty = (analysis.red_flag_detector?.total_penalty as number) ?? 0;
  total += penalty;
  return total;
}

function getRedFlagCount(analysis: AnalysisData | null): number {
  if (!analysis) return 0;
  let count = 0;
  for (const mod of Object.values(analysis)) {
    if (mod?.red_flags) count += mod.red_flags.length;
  }
  return count;
}

export default function Home() {
  const [discoveryModules, setDiscoveryModules] = useState<string[]>([]);
  const [analysisModules, setAnalysisModules] = useState<string[]>([]);
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Sort & filter
  const [sortBy, setSortBy] = useState<SortOption>("score_desc");
  const [filterBy, setFilterBy] = useState<FilterOption>("all");

  // Analysis state
  const [analysisStatus, setAnalysisStatus] = useState<AnalysisStatus | null>(null);
  const [analysisResults, setAnalysisResults] = useState<Record<string, AnalysisData>>({});
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    fetchHealth()
      .then((data) => {
        setDiscoveryModules(data.discovery_modules || []);
        setAnalysisModules(data.analysis_modules || []);
      })
      .catch(() => setError("Backend is not running. Start it with: uvicorn app.main:app"));
  }, []);

  const loadAnalysisResults = useCallback(async () => {
    const data = await getAnalysisResults();
    const mapped: Record<string, AnalysisData> = {};
    for (const r of (data.results || []) as AnalysisResultEntry[]) {
      mapped[r.coingecko_id] = {
        tokenomics_analyzer: r.tokenomics_data as AnalysisData[string],
        github_analyzer: r.github_data as AnalysisData[string],
        onchain_analyzer: r.onchain_data as AnalysisData[string],
        contract_auditor: r.audit_data as AnalysisData[string],
        holder_analyzer: r.holder_data as AnalysisData[string],
        whale_detector: r.whale_data as AnalysisData[string],
        narrative_analyzer: r.narrative_data as AnalysisData[string],
        red_flag_detector: r.red_flag_data as AnalysisData[string],
        social_tracker: r.social_data as AnalysisData[string],
        exchange_tracker: r.exchange_data as AnalysisData[string],
      };
    }
    setAnalysisResults(mapped);

    // Load alerts
    try {
      const alertData = await fetchAlerts();
      setAlerts(alertData.alerts || []);
    } catch {
      // alerts are non-critical
    }
  }, []);

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const handleScan = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await runScan();
      setScanResult(result);
      await loadAnalysisResults();
    } catch {
      setError("Scan failed. Check backend logs.");
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyse = async () => {
    setError(null);
    try {
      await startAnalysis();
      pollingRef.current = setInterval(async () => {
        const status = await getAnalysisStatus();
        setAnalysisStatus(status);
        await loadAnalysisResults();
        if (!status.running && status.completed > 0) {
          stopPolling();
          setAnalysisStatus(null);
        }
      }, 3000);
    } catch {
      setError("Analysis failed to start.");
    }
  };

  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  const getProjectAnalysis = (projectId: string | undefined): AnalysisData | null => {
    if (!projectId) return null;
    return analysisResults[projectId] || null;
  };

  const analysedCount = Object.keys(analysisResults).length;

  // Filter and sort projects
  const sortedProjects = useMemo(() => {
    if (!scanResult) return [];
    let projects = [...scanResult.projects];

    // Filter
    if (filterBy === "analysed") {
      projects = projects.filter((p) => p.id && analysisResults[p.id]);
    } else if (filterBy === "high_score") {
      projects = projects.filter((p) => p.id && getTotalScore(analysisResults[p.id] || null) >= 40);
    } else if (filterBy === "no_red_flags") {
      projects = projects.filter((p) => p.id && getRedFlagCount(analysisResults[p.id] || null) === 0);
    }

    // Sort
    projects.sort((a, b) => {
      const aAnalysis = a.id ? analysisResults[a.id] || null : null;
      const bAnalysis = b.id ? analysisResults[b.id] || null : null;

      switch (sortBy) {
        case "score_desc":
          return getTotalScore(bAnalysis) - getTotalScore(aAnalysis);
        case "score_asc":
          return getTotalScore(aAnalysis) - getTotalScore(bAnalysis);
        case "mcap_asc":
          return (a.market_cap || 0) - (b.market_cap || 0);
        case "mcap_desc":
          return (b.market_cap || 0) - (a.market_cap || 0);
        case "volume_desc":
          return (b.volume_24h || 0) - (a.volume_24h || 0);
        case "change_desc":
          return (b.price_change_24h || 0) - (a.price_change_24h || 0);
        case "red_flags":
          return getRedFlagCount(bAnalysis) - getRedFlagCount(aAnalysis);
        case "name_asc":
          return a.name.localeCompare(b.name);
        default:
          return 0;
      }
    });

    return projects;
  }, [scanResult, sortBy, filterBy, analysisResults]);

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">100x Crypto Screener</h1>
          <p className="text-sm text-gray-500">Discover early-stage projects with 100x potential</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={handleScan}
            disabled={loading}
            className="rounded-lg bg-blue-600 px-5 py-2 font-medium transition hover:bg-blue-500 disabled:opacity-50"
          >
            {loading ? "Scanning..." : "Run Scan"}
          </button>
          {scanResult && scanResult.projects.length > 0 && !analysisStatus?.running && (
            <button
              onClick={handleAnalyse}
              className="rounded-lg bg-purple-600 px-5 py-2 font-medium transition hover:bg-purple-500"
            >
              Analyse All ({scanResult.projects.length})
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-800 bg-red-950 p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {scanResult?.from_cache && (
        <div className="mb-4 rounded-lg border border-yellow-800 bg-yellow-950 p-3 text-sm text-yellow-300">
          Showing cached results (less than 6 hours old)
        </div>
      )}

      {analysisStatus?.running && (
        <div className="mb-4 rounded-lg border border-purple-800 bg-purple-950 p-4">
          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="text-purple-300">
              Analysing: {analysisStatus.current_project}
            </span>
            <span className="text-purple-400">
              {analysisStatus.completed}/{analysisStatus.total}
              {analysedCount > 0 && (
                <span className="ml-2 text-green-400">
                  &#10003; {analysedCount} analysed
                </span>
              )}
            </span>
          </div>
          <div className="h-2 rounded-full bg-purple-900">
            <div
              className="h-full rounded-full bg-purple-500 transition-all duration-500"
              style={{
                width: `${analysisStatus.total > 0 ? (analysisStatus.completed / analysisStatus.total) * 100 : 0}%`,
              }}
            />
          </div>
        </div>
      )}

      {/* Sort & Filter controls */}
      {scanResult && scanResult.projects.length > 0 && (
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500">Sort:</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as SortOption)}
              className="rounded bg-gray-800 px-3 py-1.5 text-sm text-gray-200 border border-gray-700 focus:border-blue-500 focus:outline-none"
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500">Filter:</span>
            {FILTER_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setFilterBy(opt.value)}
                className={`rounded px-3 py-1.5 text-xs font-medium transition ${
                  filterBy === opt.value
                    ? "bg-blue-600 text-white"
                    : "bg-gray-800 text-gray-400 hover:text-gray-200"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-4">
        <div className="space-y-4 lg:col-span-1">
          <ModuleStatus modules={discoveryModules} scanResult={scanResult} />
          {analysisModules.length > 0 && (
            <div className="rounded-lg border border-gray-800 bg-gray-900 p-4">
              <h2 className="mb-3 text-lg font-semibold">Analysis Modules</h2>
              <div className="space-y-2">
                {analysisModules.map((name) => {
                  const hasResults = analysedCount > 0;
                  const isRunning = analysisStatus?.running;
                  const status = isRunning ? "running" : hasResults ? "success" : "pending";
                  return (
                    <div key={name} className="flex items-center justify-between rounded bg-gray-800 px-3 py-2">
                      <span className="font-mono text-sm">{name}</span>
                      <span
                        className={`rounded px-2 py-0.5 text-xs font-medium ${
                          status === "success"
                            ? "bg-green-900 text-green-300"
                            : status === "running"
                              ? "bg-purple-900 text-purple-300"
                              : "bg-gray-700 text-gray-400"
                        }`}
                      >
                        {status}
                      </span>
                    </div>
                  );
                })}
              </div>
              {analysedCount > 0 && (
                <div className="mt-3 text-xs text-gray-500">
                  {analysedCount} projects analysed
                </div>
              )}
            </div>
          )}

          {/* Alert Feed */}
          {alerts.length > 0 && (
            <div className="rounded-lg border border-gray-800 bg-gray-900 p-4">
              <h2 className="mb-3 text-lg font-semibold">Alerts</h2>
              <AlertFeed alerts={alerts} />
            </div>
          )}
        </div>

        <div className="lg:col-span-3">
          {scanResult ? (
            <>
              <div className="mb-4 text-sm text-gray-400">
                Showing {sortedProjects.length} of {scanResult.projects.length} projects
                {analysedCount > 0 && ` | ${analysedCount} analysed`}
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {sortedProjects.map((p, i) => (
                  <ProjectCard
                    key={p.id || i}
                    project={p}
                    analysis={getProjectAnalysis(p.id)}
                  />
                ))}
              </div>
              {sortedProjects.length === 0 && (
                <p className="text-gray-500">No projects match the current filter.</p>
              )}
            </>
          ) : (
            <div className="flex h-48 items-center justify-center text-gray-600">
              Click &quot;Run Scan&quot; to discover projects
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
