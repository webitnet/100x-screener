"use client";

import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

interface ScoreCategory {
  category: string;
  score: number;
  max: number;
  fullMark: number;
}

interface Props {
  categories: {
    technology: number;
    tokenomics: number;
    onchain_traction: number;
    team_backing: number;
    community: number;
    narrative: number;
    smart_money: number;
  };
  totalScore: number;
  classification: string;
}

const CATEGORY_LABELS: Record<string, string> = {
  technology: "Tech",
  tokenomics: "Tokenomics",
  onchain_traction: "On-Chain",
  team_backing: "Team",
  community: "Community",
  narrative: "Narrative",
  smart_money: "Smart $",
};

const CATEGORY_MAX: Record<string, number> = {
  technology: 20,
  tokenomics: 20,
  onchain_traction: 20,
  team_backing: 15,
  community: 10,
  narrative: 10,
  smart_money: 5,
};

export default function ScoreRadar({ categories, totalScore, classification }: Props) {
  const data: ScoreCategory[] = Object.entries(categories).map(
    ([key, score]) => ({
      category: CATEGORY_LABELS[key] || key,
      score,
      max: CATEGORY_MAX[key] || 20,
      fullMark: CATEGORY_MAX[key] || 20,
    })
  );

  const classColor =
    classification === "Strong Buy"
      ? "text-green-400"
      : classification === "Buy"
        ? "text-emerald-400"
        : classification === "Watch"
          ? "text-yellow-400"
          : classification === "Weak"
            ? "text-orange-400"
            : "text-red-400";

  return (
    <div className="flex flex-col items-center">
      <div className="mb-1 text-center">
        <span className="text-2xl font-bold">{totalScore}</span>
        <span className="text-sm text-gray-500">/100</span>
        <span className={`ml-2 text-sm font-semibold ${classColor}`}>
          {classification}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <RadarChart data={data} cx="50%" cy="50%" outerRadius="75%">
          <PolarGrid stroke="#374151" />
          <PolarAngleAxis
            dataKey="category"
            tick={{ fill: "#9ca3af", fontSize: 11 }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, "dataMax"]}
            tick={false}
            axisLine={false}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#1f2937",
              border: "1px solid #374151",
              borderRadius: "8px",
              fontSize: "12px",
            }}
            formatter={(value, _name, entry) => [
              `${value}/${(entry.payload as ScoreCategory).max}`,
              (entry.payload as ScoreCategory).category,
            ]}
          />
          <Radar
            name="Score"
            dataKey="score"
            stroke="#3b82f6"
            fill="#3b82f6"
            fillOpacity={0.3}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
