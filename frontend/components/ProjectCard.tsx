"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { addToWatchlist } from "@/lib/api";
import HistoryModal from "./HistoryModal";

const ScoreRadar = dynamic(() => import("./ScoreRadar"), { ssr: false });

export interface Project {
  id?: string | number;
  coingecko_id?: string;
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

export interface AnalysisData {
  [moduleKey: string]: {
    project_id: string;
    red_flags?: string[];
    tokenomics_score?: number;
    github_score?: number;
    onchain_score?: number;
    audit_score?: number;
    holder_score?: number;
    fdv_to_mcap?: number | null;
    circulating_to_total?: number | null;
    stars?: number;
    commits_last_month?: number;
    tvl_usd?: number | null;
    top10_holder_pct?: number;
    is_honeypot?: boolean | null;
    [key: string]: unknown;
  };
}

function formatUsd(value: number | null | undefined): string {
  if (value == null) return "—";
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(1)}K`;
  return `$${value.toFixed(2)}`;
}

export interface ScoreBreakdown {
  final_score: number;
  classification: string;
  position_size?: string;
  categories: {
    technology: number;
    tokenomics: number;
    onchain_traction: number;
    team_backing: number;
    community: number;
    narrative: number;
    smart_money: number;
  };
}

interface Props {
  project: Project;
  analysis?: AnalysisData | null;
  scoreBreakdown?: ScoreBreakdown | null;
  onWatchlistAdd?: () => void;
  isStale?: boolean;
}

export default function ProjectCard({ project, analysis, scoreBreakdown, onWatchlistAdd, isStale }: Props) {
  const [showRadar, setShowRadar] = useState(false);
  const [watchlistAdding, setWatchlistAdding] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  const changeColor =
    (project.price_change_24h ?? 0) >= 0 ? "text-green-400" : "text-red-400";

  // All modules — always shown when analysis exists
  const ALL_MODULES: { key: string; scoreKey: string; label: string; max: number; noDataReason: string }[] = [
    { key: "tokenomics_analyzer", scoreKey: "tokenomics_score", label: "Tokenomics", max: 20, noDataReason: "No CoinGecko data" },
    { key: "github_analyzer", scoreKey: "github_score", label: "GitHub", max: 20, noDataReason: "No GitHub repo" },
    { key: "onchain_analyzer", scoreKey: "onchain_score", label: "On-Chain", max: 20, noDataReason: "No TVL / on-chain data" },
    { key: "contract_auditor", scoreKey: "audit_score", label: "Audit", max: 20, noDataReason: "No contract found" },
    { key: "holder_analyzer", scoreKey: "holder_score", label: "Holders", max: 10, noDataReason: "No holder data" },
    { key: "whale_detector", scoreKey: "smart_money_score", label: "Smart Money", max: 5, noDataReason: "No data" },
    { key: "narrative_analyzer", scoreKey: "narrative_score", label: "Narrative", max: 10, noDataReason: "No data" },
    { key: "social_tracker", scoreKey: "social_score", label: "Social", max: 10, noDataReason: "No data" },
    { key: "exchange_tracker", scoreKey: "exchange_score", label: "Exchanges", max: 8, noDataReason: "No data" },
  ];

  const scores: { label: string; value: number; max: number; noData: string | null }[] = [];
  const redFlags: string[] = [];

  if (analysis) {
    for (const mod of ALL_MODULES) {
      const modData = analysis[mod.key];
      const score = modData?.[mod.scoreKey] as number | undefined;
      scores.push({
        label: mod.label,
        value: score ?? 0,
        max: mod.max,
        noData: modData ? null : mod.noDataReason,
      });
    }

    // Collect red flags (deduplicated)
    const flagSet = new Set<string>();
    for (const mod of Object.values(analysis)) {
      if (mod?.red_flags) {
        for (const f of mod.red_flags) flagSet.add(f);
      }
    }
    flagSet.forEach((f) => redFlags.push(f));
  }

  // Penalty from red_flag_detector
  const penalty = (analysis?.red_flag_detector?.total_penalty as number) ?? 0;
  const riskLevel = analysis?.red_flag_detector?.risk_level as string | undefined;
  const narratives = (analysis?.narrative_analyzer?.matched_narratives as string[]) ?? [];

  // Use weighted final_score from backend project_scorer (0-100)
  const totalScore = scoreBreakdown?.final_score ?? 0;
  const maxTotal = 100;
  const classification = scoreBreakdown?.classification ?? "Avoid";

  return (
    <div className={`rounded-lg border bg-gray-900 p-4 transition hover:border-gray-600 ${isStale ? "border-gray-900 opacity-40 grayscale" : "border-gray-800"}`}>
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-3">
          {project.image && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={project.image} alt={project.name} className="h-8 w-8 rounded-full" />
          )}
          <div>
            <h3 className="font-semibold">{project.name}</h3>
            <span className="text-xs text-gray-500">{project.ticker}</span>
          </div>
        </div>
        {analysis && scoreBreakdown && (
          <div className="text-right">
            <div className={`rounded px-2 py-1 text-sm font-bold ${
              totalScore >= 65 ? "bg-green-900 text-green-300" :
              totalScore >= 50 ? "bg-yellow-900 text-yellow-300" :
              totalScore >= 30 ? "bg-orange-900 text-orange-300" :
              "bg-red-900 text-red-300"
            }`}>
              {totalScore}/{maxTotal}
            </div>
            <div className="mt-1 text-[10px] font-semibold text-gray-400">{classification}</div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2 text-sm">
        <div>
          <span className="text-gray-500">Price</span>
          <p className="font-mono">{project.price != null ? `$${project.price.toPrecision(4)}` : "—"}</p>
        </div>
        <div>
          <span className="text-gray-500">MCap</span>
          <p className="font-mono">{formatUsd(project.market_cap)}</p>
        </div>
        <div>
          <span className="text-gray-500">Vol 24h</span>
          <p className="font-mono">{formatUsd(project.volume_24h)}</p>
        </div>
        <div>
          <span className="text-gray-500">Vol/MCap</span>
          <p className="font-mono">
            {project.volume_to_mcap_ratio != null
              ? `${(project.volume_to_mcap_ratio * 100).toFixed(1)}%`
              : "—"}
          </p>
        </div>
        <div>
          <span className="text-gray-500">Age</span>
          <p className="font-mono">{project.age_days != null ? `${project.age_days}d` : "—"}</p>
        </div>
        <div>
          <span className="text-gray-500">24h</span>
          <p className={`font-mono ${changeColor}`}>
            {project.price_change_24h != null
              ? `${project.price_change_24h > 0 ? "+" : ""}${project.price_change_24h.toFixed(1)}%`
              : "—"}
          </p>
        </div>
      </div>

      {analysis && (
        <div className="mt-3 space-y-1">
          {scores.map((s) => (
            <div key={s.label} className="flex items-center gap-2 text-xs">
              <span className="w-20 text-gray-500">{s.label}</span>
              {s.noData ? (
                <span className="flex-1 text-gray-600 italic">{s.noData}</span>
              ) : (
                <>
                  <div className="h-1.5 flex-1 rounded-full bg-gray-800">
                    <div
                      className={`h-full rounded-full ${s.value === 0 ? "bg-gray-700" : "bg-blue-500"}`}
                      style={{ width: `${(s.value / s.max) * 100}%` }}
                    />
                  </div>
                  <span className="w-8 text-right font-mono text-gray-400">{s.value}/{s.max}</span>
                </>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Penalty bar */}
      {analysis && penalty < 0 && (
        <div className="mt-2 flex items-center gap-2 text-xs">
          <span className="w-20 text-red-500">Penalty</span>
          <span className="font-mono text-red-400">{penalty}</span>
          {riskLevel && (
            <span className={`ml-auto rounded px-1.5 py-0.5 text-[10px] font-medium ${
              riskLevel === "critical" ? "bg-red-900 text-red-300" :
              riskLevel === "high" ? "bg-orange-900 text-orange-300" :
              "bg-yellow-900 text-yellow-300"
            }`}>
              {riskLevel} risk
            </span>
          )}
        </div>
      )}

      {/* Narrative tags */}
      {narratives.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {narratives.map((n) => (
            <span key={n} className="rounded bg-indigo-950 px-1.5 py-0.5 text-[10px] text-indigo-300">
              {n}
            </span>
          ))}
        </div>
      )}

      {/* Red flags */}
      {redFlags.length > 0 && (
        <div className="mt-2 space-y-1">
          {redFlags.map((flag, i) => (
            <div key={i} className="rounded bg-red-950 px-2 py-1 text-xs text-red-400">
              {flag}
            </div>
          ))}
        </div>
      )}

      {/* History button */}
      {(project.coingecko_id || project.id) && (
        <button
          onClick={() => setShowHistory(true)}
          className="mt-3 w-full rounded bg-gray-800 px-2 py-1 text-xs text-gray-400 hover:text-gray-200 transition"
        >
          History
        </button>
      )}

      {showHistory && (project.coingecko_id || project.id) && (
        <HistoryModal
          coingeckoId={String(project.coingecko_id || project.id)}
          projectName={project.name}
          onClose={() => setShowHistory(false)}
        />
      )}

      {/* ScoreRadar toggle */}
      {analysis && scoreBreakdown && (
        <div className="mt-3">
          <button
            onClick={() => setShowRadar(!showRadar)}
            className="w-full rounded bg-gray-800 px-2 py-1 text-xs text-gray-400 hover:text-gray-200 transition"
          >
            {showRadar ? "Hide Radar" : "Show Radar"}
          </button>
          {showRadar && (
            <div className="mt-2">
              <ScoreRadar
                categories={scoreBreakdown.categories}
                totalScore={totalScore}
                classification={classification}
              />
            </div>
          )}
        </div>
      )}

      {/* Watchlist button */}
      {project.coingecko_id && (
        <button
          disabled={watchlistAdding}
          onClick={async () => {
            setWatchlistAdding(true);
            try {
              await addToWatchlist(
                project.coingecko_id!,
                project.name,
                project.ticker,
              );
              onWatchlistAdd?.();
            } finally {
              setWatchlistAdding(false);
            }
          }}
          className="mt-2 w-full rounded bg-gray-800 px-2 py-1.5 text-xs text-gray-400 hover:bg-gray-700 hover:text-gray-200 transition"
        >
          {watchlistAdding ? "Adding..." : "+ Watchlist"}
        </button>
      )}
    </div>
  );
}
