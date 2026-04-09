"use client";

export interface AlertItem {
  id: number;
  coingecko_id: string;
  project_name: string;
  alert_type: string;
  severity: string;
  title: string;
  message: string;
  score: number | null;
  sent_telegram: boolean;
  sent_email: boolean;
  created_at: string | null;
}

interface Props {
  alerts: AlertItem[];
}

const TYPE_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  score_high: { bg: "bg-green-950", text: "text-green-400", label: "Score" },
  red_flag: { bg: "bg-red-950", text: "text-red-400", label: "Red Flag" },
  whale: { bg: "bg-blue-950", text: "text-blue-400", label: "Whale" },
  listing: { bg: "bg-purple-950", text: "text-purple-400", label: "Listing" },
};

const SEVERITY_DOT: Record<string, string> = {
  critical: "bg-red-500",
  warning: "bg-yellow-500",
  info: "bg-green-500",
};

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return "";
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function AlertFeed({ alerts }: Props) {
  if (alerts.length === 0) {
    return (
      <div className="rounded-lg border border-gray-800 bg-gray-900 p-4 text-center text-sm text-gray-500">
        No alerts yet. Run analysis to generate alerts.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {alerts.map((alert) => {
        const style = TYPE_STYLES[alert.alert_type] || TYPE_STYLES.score_high;
        const dot = SEVERITY_DOT[alert.severity] || SEVERITY_DOT.info;

        return (
          <div
            key={alert.id}
            className={`rounded-lg border border-gray-800 ${style.bg} p-3`}
          >
            <div className="flex items-center gap-2">
              <span className={`h-2 w-2 rounded-full ${dot}`} />
              <span
                className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${style.text} bg-black/20`}
              >
                {style.label}
              </span>
              <span className={`flex-1 text-sm font-medium ${style.text}`}>
                {alert.project_name}
              </span>
              {alert.score != null && (
                <span className="text-xs text-gray-400">
                  {alert.score.toFixed(0)}/100
                </span>
              )}
              <span className="text-[10px] text-gray-600">
                {timeAgo(alert.created_at)}
              </span>
            </div>
            <p className="mt-1 text-xs text-gray-400">{alert.title}</p>
          </div>
        );
      })}
    </div>
  );
}
