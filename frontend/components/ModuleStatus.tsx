"use client";

interface ModuleStatusProps {
  modules: string[];
  scanResult: {
    total_modules: number;
    successful: number;
    failed: number;
    warnings: number;
    failed_modules: { name: string; message: string }[];
  } | null;
}

export default function ModuleStatus({ modules, scanResult }: ModuleStatusProps) {
  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900 p-4">
      <h2 className="mb-3 text-lg font-semibold">Module Status</h2>
      <div className="space-y-2">
        {modules.map((name) => {
          const failed = scanResult?.failed_modules.find((f) => f.name === name);
          const status = !scanResult
            ? "pending"
            : failed
              ? "error"
              : "success";

          return (
            <div key={name} className="flex items-center justify-between rounded bg-gray-800 px-3 py-2">
              <span className="font-mono text-sm">{name}</span>
              <span
                className={`rounded px-2 py-0.5 text-xs font-medium ${
                  status === "success"
                    ? "bg-green-900 text-green-300"
                    : status === "error"
                      ? "bg-red-900 text-red-300"
                      : "bg-gray-700 text-gray-400"
                }`}
              >
                {status}
              </span>
            </div>
          );
        })}
      </div>
      {scanResult && (
        <div className="mt-3 text-xs text-gray-500">
          {scanResult.successful}/{scanResult.total_modules} modules OK
        </div>
      )}
    </div>
  );
}
