"use client";

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

interface Props {
  project: Project;
  analysis?: AnalysisData | null;
}

export default function ProjectCard({ project, analysis }: Props) {
  const changeColor =
    (project.price_change_24h ?? 0) >= 0 ? "text-green-400" : "text-red-400";

  // All modules — always shown when analysis exists
  const ALL_MODULES: { key: string; scoreKey: string; label: string; max: number; noDataReason: string }[] = [
    { key: "tokenomics_analyzer", scoreKey: "tokenomics_score", label: "Tokenomics", max: 20, noDataReason: "No CoinGecko data" },
    { key: "github_analyzer", scoreKey: "github_score", label: "GitHub", max: 20, noDataReason: "No GitHub repo" },
    { key: "onchain_analyzer", scoreKey: "onchain_score", label: "On-Chain", max: 20, noDataReason: "No TVL / on-chain data" },
    { key: "contract_auditor", scoreKey: "audit_score", label: "Audit", max: 20, noDataReason: "No contract found" },
    { key: "holder_analyzer", scoreKey: "holder_score", label: "Holders", max: 10, noDataReason: "No holder data" },
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

    for (const mod of Object.values(analysis)) {
      if (mod?.red_flags) redFlags.push(...mod.red_flags);
    }
  }

  const totalScore = scores.reduce((sum, s) => sum + s.value, 0);
  const maxTotal = ALL_MODULES.reduce((sum, m) => sum + m.max, 0);

  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900 p-4 transition hover:border-gray-600">
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
        {analysis && (
          <div className={`rounded px-2 py-1 text-sm font-bold ${
            totalScore >= 60 ? "bg-green-900 text-green-300" :
            totalScore >= 40 ? "bg-yellow-900 text-yellow-300" :
            "bg-red-900 text-red-300"
          }`}>
            {totalScore}/{maxTotal}
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

      {redFlags.length > 0 && (
        <div className="mt-3 space-y-1">
          {redFlags.map((flag, i) => (
            <div key={i} className="rounded bg-red-950 px-2 py-1 text-xs text-red-400">
              {flag}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
