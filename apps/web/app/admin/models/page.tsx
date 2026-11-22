"use client";

import { useQuery } from "@tanstack/react-query";
import { Boxes, Cpu, Gauge, ShieldCheck } from "lucide-react";
import { useMemo } from "react";

import { getModels, type ModelVersion } from "@/lib/api";
import { formatDate, titleCase } from "@/lib/utils";
import {
  Badge,
  Card,
  CardHeader,
  EmptyState,
  ErrorState,
  PageHeader,
  Skeleton,
  Stat,
} from "@/components/ui";

function metricValue(value: unknown) {
  if (typeof value === "number") {
    return Number.isInteger(value) ? value.toString() : value.toFixed(4);
  }
  if (typeof value === "string" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

function flattenMetrics(metrics: Record<string, unknown>): [string, unknown][] {
  const entries: [string, unknown][] = [];
  Object.entries(metrics).forEach(([key, value]) => {
    if (value && typeof value === "object" && !Array.isArray(value)) {
      Object.entries(value as Record<string, unknown>).forEach(([nestedKey, nestedValue]) => {
        entries.push([`${key}.${nestedKey}`, nestedValue]);
      });
    } else {
      entries.push([key, value]);
    }
  });
  return entries;
}

function ModelRow({ model }: { model: ModelVersion }) {
  const metrics = flattenMetrics(model.metrics);
  return (
    <tr className="border-t border-ink-100 align-top">
      <td className="px-5 py-3">
        <p className="text-xs font-medium text-ink-900">{model.name}</p>
        <p className="font-mono text-[10px] text-ink-400">v{model.version}</p>
      </td>
      <td className="px-5 py-3">
        <Badge tone="accent">{model.task}</Badge>
      </td>
      <td className="px-5 py-3 text-xs text-ink-500">
        {model.runtime}
        <span className="ml-1 text-[10px] text-ink-400">· {model.precision}</span>
      </td>
      <td className="px-5 py-3">
        <div className="flex max-w-md flex-wrap gap-1">
          {metrics.slice(0, 6).map(([key, value]) => (
            <span
              key={key}
              className="rounded bg-ink-100 px-1.5 py-0.5 font-mono text-[10px] text-ink-600"
              title={key}
            >
              {key.split(".").pop()}: {metricValue(value)}
            </span>
          ))}
          {metrics.length > 6 ? (
            <span className="rounded bg-ink-100 px-1.5 py-0.5 text-[10px] text-ink-500">
              +{metrics.length - 6}
            </span>
          ) : null}
        </div>
      </td>
      <td className="px-5 py-3 text-right">
        <Badge tone={model.approved ? "success" : "warning"}>{model.approved ? "approved" : "candidate"}</Badge>
      </td>
      <td className="px-5 py-3 text-right text-[11px] text-ink-400">{formatDate(model.created_at)}</td>
    </tr>
  );
}

export default function ModelsPage() {
  const models = useQuery({ queryKey: ["models"], queryFn: getModels });

  const summary = useMemo(() => {
    const list = models.data ?? [];
    const tasks = new Set(list.map((model) => model.task));
    return {
      total: list.length,
      tasks: tasks.size,
      approved: list.filter((model) => model.approved).length,
      latest: list[0],
    };
  }, [models.data]);

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Admin"
        title="Model registry"
        description="Every training run registers a version with metrics, runtime and artifact path. Approval is a separate gate."
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Registered models" value={summary.total} icon={Boxes} tone="accent" />
        <Stat label="Task types" value={summary.tasks} icon={Cpu} />
        <Stat label="Approved" value={summary.approved} icon={ShieldCheck} tone="success" />
        <Stat
          label="Latest version"
          value={summary.latest ? `v${summary.latest.version}` : "—"}
          hint={summary.latest ? summary.latest.name : undefined}
          icon={Gauge}
        />
      </div>

      {models.isError ? <ErrorState message={(models.error as Error).message} /> : null}

      <Card>
        <CardHeader
          icon={Boxes}
          title="Versions"
          description="Metrics are read directly from the training artifacts"
        />
        {models.isLoading ? (
          <div className="space-y-2 p-5">
            {Array.from({ length: 4 }).map((_, index) => (
              <Skeleton key={index} className="h-10" />
            ))}
          </div>
        ) : models.data && models.data.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="text-[10px] uppercase tracking-wider text-ink-400">
                  <th className="px-5 pb-2 font-medium">Model</th>
                  <th className="px-5 pb-2 font-medium">Task</th>
                  <th className="px-5 pb-2 font-medium">Runtime</th>
                  <th className="px-5 pb-2 font-medium">Metrics</th>
                  <th className="px-5 pb-2 text-right font-medium">Stage</th>
                  <th className="px-5 pb-2 text-right font-medium">Created</th>
                </tr>
              </thead>
              <tbody>
                {models.data.map((model) => (
                  <ModelRow key={model.id} model={model} />
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No models registered" description="Run the training scripts to register baselines." />
        )}
      </Card>

      {models.data ? (
        <Card className="p-5">
          <p className="text-xs font-semibold text-ink-900">Metric detail</p>
          <div className="mt-3 space-y-4">
            {models.data.map((model) => (
              <div key={model.id}>
                <p className="text-[11px] font-medium text-ink-600">
                  {titleCase(model.task)} · {model.name} v{model.version}
                </p>
                <div className="mt-1 grid gap-x-6 gap-y-1 sm:grid-cols-2 lg:grid-cols-3">
                  {flattenMetrics(model.metrics).map(([key, value]) => (
                    <div key={key} className="flex items-baseline justify-between gap-3 border-b border-dashed border-ink-100 py-0.5">
                      <span className="text-[10px] text-ink-400">{key}</span>
                      <span className="font-mono text-[10px] text-ink-700">{metricValue(value)}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Card>
      ) : null}
    </div>
  );
}
