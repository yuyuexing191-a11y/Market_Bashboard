import { useCallback, useEffect, useState } from "react";

type HealthResponse = {
  status?: "ok" | "degraded";
  database?: "up" | "down";
  detail?: string;
};

type HealthState =
  | { kind: "loading" }
  | { kind: "ready"; response: HealthResponse; httpStatus: number }
  | { kind: "error"; message: string };

const HEALTH_ENDPOINT = "/api/health";

function StatusIndicator({ state }: { state: "up" | "down" | "loading" }) {
  return <span className={`status-dot status-dot--${state}`} aria-hidden="true" />;
}

function ServiceRow({
  label,
  value,
}: {
  label: string;
  value: "up" | "down" | "loading";
}) {
  const isLoading = value === "loading";
  const text = isLoading ? "检查中" : value === "up" ? "正常" : "不可用";

  return (
    <div className="service-row">
      <div className="service-name">
        <StatusIndicator state={value} />
        <span>{label}</span>
      </div>
      <span className={`service-value service-value--${value}`}>{text}</span>
    </div>
  );
}

export function App() {
  const [health, setHealth] = useState<HealthState>({ kind: "loading" });

  const loadHealth = useCallback(async () => {
    setHealth({ kind: "loading" });

    try {
      const response = await fetch(HEALTH_ENDPOINT, {
        headers: { Accept: "application/json" },
      });
      const body = (await response.json()) as HealthResponse;

      setHealth({
        kind: "ready",
        response: body,
        httpStatus: response.status,
      });
    } catch {
      setHealth({
        kind: "error",
        message: "无法连接后端服务",
      });
    }
  }, []);

  useEffect(() => {
    void loadHealth();
  }, [loadHealth]);

  const database =
    health.kind === "ready"
      ? health.response.database === "up"
        ? "up"
        : "down"
      : health.kind === "loading"
        ? "loading"
        : "down";
  const service =
    health.kind === "ready"
      ? health.response.status === "ok"
        ? "up"
        : "down"
      : health.kind === "loading"
        ? "loading"
        : "down";

  return (
    <main className="page-shell">
      <section className="status-panel" aria-labelledby="page-title">
        <header className="panel-header">
          <div>
            <p className="eyebrow">MARKET DASHBOARD / ISSUE 04</p>
            <h1 id="page-title">系统状态</h1>
          </div>
          <div className="pulse-mark" aria-label="市场看板">
            <span />
            <span />
            <span />
          </div>
        </header>

        <div className="service-list" aria-live="polite">
          <ServiceRow label="后端服务" value={service} />
          <ServiceRow label="数据库" value={database} />
        </div>

        <div className="connection-meta">
          <div>
            <span className="meta-label">API 地址</span>
            <code>{HEALTH_ENDPOINT}</code>
          </div>
          <div>
            <span className="meta-label">HTTP 状态</span>
            <span className="http-code">
              {health.kind === "ready" ? health.httpStatus : "--"}
            </span>
          </div>
        </div>

        {health.kind === "ready" && health.response.detail ? (
          <p className="status-detail">{health.response.detail}</p>
        ) : null}
        {health.kind === "error" ? <p className="status-detail status-detail--error">{health.message}</p> : null}

        <button className="refresh-button" type="button" onClick={() => void loadHealth()}>
          <span aria-hidden="true">↻</span>
          重新检查
        </button>
      </section>
    </main>
  );
}
