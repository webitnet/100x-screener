"use client";

import { useEffect, useState } from "react";
import { getAnalysisHistory } from "@/lib/api";

interface Snapshot {
  analysed_at: string | null;
  final_score: number | null;
  classification: string | null;
  score_categories: Record<string, number> | null;
  red_flags: string[];
  risk_level: string | null;
  market_cap: number | null;
  fdv: number | null;
  top10_holder_pct: number | null;
  holder_count: number | null;
  commits_last_month: number | null;
  tvl_usd: number | null;
}

interface Props {
  coingeckoId: string;
  projectName: string;
  onClose: () => void;
}

function fmtUsd(v: number | null | undefined): string {
  if (v == null) return "—";
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(1)}K`;
  return `$${v.toFixed(2)}`;
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString();
}

type Delta = { value: string; color: string } | null;

function delta(
  curr: number | null | undefined,
  prev: number | null | undefined,
  opts: { higherIsBetter?: boolean; suffix?: string; fmt?: (n: number) => string } = {}
): Delta {
  if (curr == null || prev == null) return null;
  const diff = curr - prev;
  if (diff === 0) return null;
  const higherIsBetter = opts.higherIsBetter ?? true;
  const good = higherIsBetter ? diff > 0 : diff < 0;
  const color = good ? "text-green-400" : "text-red-400";
  const sign = diff > 0 ? "+" : "";
  const formatted = opts.fmt ? opts.fmt(diff) : diff.toFixed(2);
  return { value: `${sign}${formatted}${opts.suffix ?? ""}`, color };
}

export default function HistoryModal({ coingeckoId, projectName, onClose }: Props) {
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAnalysisHistory(coingeckoId)
      .then((data) => setSnapshots(data.snapshots || []))
      .finally(() => setLoading(false));
  }, [coingeckoId]);

  const curr = snapshots[0];
  const prev = snapshots[1];

  // Red flag diff (added / removed between curr and prev)
  const currFlags = new Set(curr?.red_flags ?? []);
  const prevFlags = new Set(prev?.red_flags ?? []);
  const added = [...currFlags].filter((f) => !prevFlags.has(f));
  const removed = [...prevFlags].filter((f) => !currFlags.has(f));

  // Score trend (min/max for sparkline scaling)
  const scores = snapshots
    .map((s) => s.final_score)
    .filter((s): s is number => s != null)
    .reverse(); // oldest → newest for chart

  const maxScore = Math.max(100, ...scores);
  const minScore = Math.min(0, ...scores);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <div
        className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-lg border border-gray-700 bg-gray-900 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold">{projectName} — History</h2>
          <button
            onClick={onClose}
            className="rounded px-3 py-1 text-gray-400 hover:bg-gray-800 hover:text-white"
          >
            ✕
          </button>
        </div>

        {loading && <p className="text-gray-500">Loading…</p>}

        {!loading && snapshots.length === 0 && (
          <p className="text-gray-500">No history yet. Run Analyse All to create snapshots.</p>
        )}

        {!loading && snapshots.length > 0 && (
          <>
            {/* Score trend sparkline */}
            {scores.length >= 2 && (
              <div className="mb-5">
                <div className="mb-2 text-xs text-gray-500">
                  Score trend ({scores.length} runs)
                </div>
                <svg viewBox="0 0 400 80" className="w-full">
                  <polyline
                    fill="none"
                    stroke="#a855f7"
                    strokeWidth="2"
                    points={scores
                      .map((s, i) => {
                        const x = (i / Math.max(1, scores.length - 1)) * 400;
                        const y =
                          80 - ((s - minScore) / Math.max(1, maxScore - minScore)) * 80;
                        return `${x},${y}`;
                      })
                      .join(" ")}
                  />
                  {scores.map((s, i) => {
                    const x = (i / Math.max(1, scores.length - 1)) * 400;
                    const y =
                      80 - ((s - minScore) / Math.max(1, maxScore - minScore)) * 80;
                    return <circle key={i} cx={x} cy={y} r="3" fill="#a855f7" />;
                  })}
                </svg>
              </div>
            )}

            {/* Diff: latest vs previous */}
            {prev && (
              <div className="mb-5 rounded border border-gray-800 bg-gray-950 p-3">
                <div className="mb-2 text-xs font-semibold text-gray-400">
                  Change since previous run ({fmtDate(prev.analysed_at)})
                </div>
                <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                  <DiffRow label="Score" curr={curr.final_score} prev={prev.final_score} suffix="/100" />
                  <DiffRow label="MCap" curr={curr.market_cap} prev={prev.market_cap} fmt={fmtUsd} />
                  <DiffRow label="FDV" curr={curr.fdv} prev={prev.fdv} fmt={fmtUsd} />
                  <DiffRow label="Holders" curr={curr.holder_count} prev={prev.holder_count} fmt={(n) => n.toFixed(0)} />
                  <DiffRow label="Top-10 %" curr={curr.top10_holder_pct} prev={prev.top10_holder_pct} higherIsBetter={false} suffix="%" />
                  <DiffRow label="Commits 30d" curr={curr.commits_last_month} prev={prev.commits_last_month} fmt={(n) => n.toFixed(0)} />
                </div>

                {(added.length > 0 || removed.length > 0) && (
                  <div className="mt-3 space-y-1 text-xs">
                    {added.map((f) => (
                      <div key={`a-${f}`} className="text-red-400">+ {f}</div>
                    ))}
                    {removed.map((f) => (
                      <div key={`r-${f}`} className="text-green-400">− {f} (resolved)</div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Raw snapshot list */}
            <div className="space-y-2">
              <div className="text-xs font-semibold text-gray-400">All snapshots</div>
              {snapshots.map((s, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between rounded bg-gray-800 px-3 py-2 text-sm"
                >
                  <span className="text-gray-400">{fmtDate(s.analysed_at)}</span>
                  <span>
                    <span className="font-mono font-semibold">{s.final_score ?? "—"}/100</span>
                    <span className="ml-2 text-xs text-gray-500">{s.classification}</span>
                  </span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function DiffRow({
  label,
  curr,
  prev,
  higherIsBetter = true,
  suffix,
  fmt,
}: {
  label: string;
  curr: number | null | undefined;
  prev: number | null | undefined;
  higherIsBetter?: boolean;
  suffix?: string;
  fmt?: (n: number) => string;
}) {
  const d = delta(curr, prev, { higherIsBetter, suffix, fmt });
  const currStr = curr == null ? "—" : fmt ? fmt(curr) : `${curr}${suffix ?? ""}`;
  return (
    <div className="flex justify-between">
      <span className="text-gray-500">{label}</span>
      <span>
        <span className="text-gray-200">{currStr}</span>
        {d && <span className={`ml-2 ${d.color}`}>{d.value}</span>}
      </span>
    </div>
  );
}
