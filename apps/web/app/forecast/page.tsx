"use client";

import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  CalendarClock,
  PackageCheck,
  Search,
  TrendingUp,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import {
  getForecast,
  getForecastOverview,
  getPart,
  searchParts,
  type Forecast,
  type OverviewItem,
} from "@/lib/api";
import { cn, formatNumber, formatPercent, riskTone } from "@/lib/utils";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorState,
  Input,
  PageHeader,
  ProgressBar,
  Select,
  Skeleton,
} from "@/components/ui";

type PartRef = { id: number; part_number: string; name: string };

function useDebounced<T>(value: T, delay = 250) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

function OverviewRow({ item, onSelect }: { item: OverviewItem; onSelect: (part: PartRef) => void }) {
  return (
    <tr className="border-t border-ink-100 hover:bg-ink-50/70">
      <td className="px-4 py-2.5">
        <button
          type="button"
          onClick={() =>
            onSelect({ id: item.part_id, part_number: item.part_number, name: item.name })
          }
          className="text-left font-mono text-xs font-medium text-ink-900 hover:text-accent-600"
        >
          {item.part_number}
        </button>
        <p className="text-[11px] text-ink-500">{item.name}</p>
      </td>
      <td className="px-4 py-2.5 text-right text-xs tabular-nums text-ink-700">
        {formatNumber(item.current_stock)}
      </td>
      <td className="px-4 py-2.5 text-right text-xs tabular-nums text-ink-700">
        {formatNumber(item.expected_30d_demand, 1)}
      </td>
      <td className="px-4 py-2.5 text-right">
        <Badge tone={riskTone(item.risk_level)}>{formatPercent(item.shortage_risk, 0)}</Badge>
      </td>
    </tr>
  );
}

function ForecastPanel({ forecast }: { forecast: Forecast }) {
  const maxImpact = Math.max(...forecast.drivers.map((driver) => Math.abs(driver.impact)), 0.0001);

  return (
    <div className="space-y-4">
      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-ink-100 px-5 py-4">
          <div>
            <Link
              href={`/parts/${forecast.part_id}`}
              className="font-mono text-xs font-medium text-ink-900 hover:text-accent-600"
            >
              {forecast.part_number}
            </Link>
            <p className="text-sm text-ink-600">{forecast.part_name}</p>
            <p className="mt-0.5 text-[11px] text-ink-400">
              {forecast.model_name} · v{forecast.model_version} · {forecast.horizon_days}-day horizon
            </p>
          </div>
          <Badge tone={riskTone(forecast.risk_level)}>{forecast.risk_level} risk</Badge>
        </div>

        <div className="grid grid-cols-2 gap-4 px-5 py-4 sm:grid-cols-4">
          <div>
            <p className="text-[10px] uppercase tracking-wide text-ink-400">Expected demand</p>
            <p className="mt-1 text-2xl font-semibold tabular-nums text-ink-950">
              {formatNumber(forecast.expected_demand, 1)}
            </p>
            <p className="text-[10px] text-ink-400">
              {formatNumber(forecast.lower_bound, 1)}–{formatNumber(forecast.upper_bound, 1)} band
            </p>
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-wide text-ink-400">Stock now</p>
            <p className="mt-1 text-2xl font-semibold tabular-nums text-ink-950">
              {formatNumber(forecast.current_stock)}
            </p>
            <p className="text-[10px] text-ink-400">across locations</p>
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-wide text-ink-400">Projected stock</p>
            <p
              className={cn(
                "mt-1 text-2xl font-semibold tabular-nums",
                forecast.predicted_stock < 0 ? "text-rose-600" : "text-ink-950",
              )}
            >
              {formatNumber(forecast.predicted_stock, 1)}
            </p>
            <p className="text-[10px] text-ink-400">end of horizon</p>
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-wide text-ink-400">Reorder qty</p>
            <p className="mt-1 text-2xl font-semibold tabular-nums text-ink-950">
              {formatNumber(forecast.reorder_quantity, 0)}
            </p>
            <p className="text-[10px] text-ink-400">suggested</p>
          </div>
        </div>

        <div className="border-t border-ink-100 px-5 py-4">
          <div className="flex items-center justify-between text-xs">
            <span className="text-ink-500">Shortage probability</span>
            <span className="font-semibold tabular-nums text-ink-900">
              {formatPercent(forecast.shortage_probability, 1)}
            </span>
          </div>
          <div className="mt-2">
            <ProgressBar
              value={forecast.shortage_probability}
              tone={
                forecast.shortage_probability > 0.6
                  ? "danger"
                  : forecast.shortage_probability > 0.3
                    ? "warning"
                    : "success"
              }
            />
          </div>
        </div>

        {forecast.warnings.length > 0 ? (
          <div className="space-y-1 bg-amber-50/70 px-5 py-3">
            {forecast.warnings.map((warning) => (
              <p key={warning} className="flex items-start gap-2 text-[11px] text-amber-700">
                <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" /> {warning}
              </p>
            ))}
          </div>
        ) : null}
      </Card>

      <Card>
        <CardHeader
          icon={TrendingUp}
          title="Demand drivers"
          description="Local counterfactual sensitivity around the median feature profile"
        />
        <div className="space-y-3 px-5 py-4">
          {forecast.drivers.length === 0 ? (
            <EmptyState title="No driver breakdown available" />
          ) : (
            forecast.drivers.map((driver) => {
              const positive = driver.impact >= 0;
              return (
                <div key={driver.feature}>
                  <div className="flex items-center justify-between text-xs">
                    <span className="capitalize text-ink-600">{driver.feature.replace(/_/g, " ")}</span>
                    <span
                      className={cn(
                        "flex items-center gap-1 tabular-nums",
                        positive ? "text-rose-600" : "text-emerald-600",
                      )}
                    >
                      {positive ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
                      {positive ? "+" : ""}
                      {driver.impact.toFixed(2)}
                    </span>
                  </div>
                  <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-ink-100">
                    <div
                      className={cn("h-full rounded-full", positive ? "bg-rose-400" : "bg-emerald-400")}
                      style={{ width: `${(Math.abs(driver.impact) / maxImpact) * 100}%` }}
                    />
                  </div>
                </div>
              );
            })
          )}
        </div>
      </Card>

      <Card className="p-4">
        <p className="text-[10px] uppercase tracking-wide text-ink-400">Model metrics</p>
        <div className="mt-2 grid grid-cols-3 gap-3">
          {Object.entries(forecast.metrics.model ?? {}).slice(0, 3).map(([key, value]) => (
            <div key={key}>
              <p className="text-[10px] uppercase tracking-wide text-ink-400">{key}</p>
              <p className="text-sm font-semibold tabular-nums text-ink-900">
                {typeof value === "number" ? value.toFixed(3) : String(value)}
              </p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function ForecastWorkspace() {
  const searchParams = useSearchParams();
  const partParam = searchParams.get("part");

  const [limit, setLimit] = useState(8);
  const [horizon, setHorizon] = useState(30);
  const [selectedPart, setSelectedPart] = useState<PartRef | null>(null);
  const [partQuery, setPartQuery] = useState("");
  const [showPicker, setShowPicker] = useState(false);
  const debouncedPartQuery = useDebounced(partQuery);

  const overview = useQuery({
    queryKey: ["forecast-overview", limit],
    queryFn: () => getForecastOverview(limit),
  });

  const preselected = useQuery({
    queryKey: ["part", Number(partParam)],
    queryFn: () => getPart(Number(partParam)),
    enabled: Boolean(partParam) && Number.isFinite(Number(partParam)),
  });

  useEffect(() => {
    if (preselected.data) {
      setSelectedPart({
        id: preselected.data.id,
        part_number: preselected.data.part_number,
        name: preselected.data.name,
      });
    }
  }, [preselected.data]);

  const pickerResults = useQuery({
    queryKey: ["part-picker", debouncedPartQuery],
    queryFn: () => searchParts({ query: debouncedPartQuery, limit: 6 }),
    enabled: debouncedPartQuery.length >= 2,
  });

  const forecast = useQuery({
    queryKey: ["forecast", selectedPart?.id, horizon],
    queryFn: () => getForecast(selectedPart!.id, horizon),
    enabled: Boolean(selectedPart),
  });

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Demand forecasting"
        title="See stock risk before it hits the line"
        description="Gradient-boosted demand model with quantile bands, shortage probability and a suggested reorder quantity."
        actions={
          <div className="flex items-center gap-2">
            <CalendarClock className="h-4 w-4 text-ink-400" />
            <Select
              value={horizon}
              onChange={(event) => setHorizon(Number(event.target.value))}
              className="h-9 w-[130px] text-xs"
            >
              {[7, 14, 30, 60, 90].map((days) => (
                <option key={days} value={days}>
                  {days} days
                </option>
              ))}
            </Select>
          </div>
        }
      />

      <div className="grid gap-4 xl:grid-cols-[1.05fr_1fr]">
        <div className="space-y-4">
          <Card className="p-4">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
              <Input
                value={partQuery}
                onChange={(event) => {
                  setPartQuery(event.target.value);
                  setShowPicker(true);
                }}
                onFocus={() => setShowPicker(true)}
                placeholder="Search a part to forecast — number or name"
                className="pl-9"
              />
              {showPicker && debouncedPartQuery.length >= 2 ? (
                <div className="absolute z-20 mt-1 w-full overflow-hidden rounded-lg border border-ink-200 bg-white shadow-lg">
                  {pickerResults.data && pickerResults.data.items.length > 0 ? (
                    pickerResults.data.items.map((part) => (
                      <button
                        key={part.id}
                        type="button"
                        onClick={() => {
                          setSelectedPart({ id: part.id, part_number: part.part_number, name: part.name });
                          setPartQuery("");
                          setShowPicker(false);
                        }}
                        className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-xs hover:bg-ink-50"
                      >
                        <span className="font-mono text-ink-900">{part.part_number}</span>
                        <span className="truncate text-ink-500">{part.name}</span>
                      </button>
                    ))
                  ) : (
                    <p className="px-3 py-2 text-xs text-ink-400">
                      {pickerResults.isLoading ? "Searching…" : "No matches"}
                    </p>
                  )}
                </div>
              ) : null}
            </div>
          </Card>

          <Card>
            <CardHeader
              icon={TrendingUp}
              title="Highest shortage risk"
              description={overview.data ? `${overview.data.method} · ${overview.data.as_of}` : "30-day preview"}
              action={
                <Select
                  value={limit}
                  onChange={(event) => setLimit(Number(event.target.value))}
                  className="h-8 w-[90px] text-xs"
                >
                  {[5, 8, 12, 20].map((value) => (
                    <option key={value} value={value}>
                      Top {value}
                    </option>
                  ))}
                </Select>
              }
            />
            {overview.isError ? (
              <div className="p-5">
                <ErrorState message={(overview.error as Error).message} />
              </div>
            ) : overview.isLoading ? (
              <div className="space-y-2 p-5">
                {Array.from({ length: 6 }).map((_, index) => (
                  <Skeleton key={index} className="h-9" />
                ))}
              </div>
            ) : overview.data && overview.data.items.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead>
                    <tr className="text-[10px] uppercase tracking-wider text-ink-400">
                      <th className="px-4 pb-2 pt-2 font-medium">Part</th>
                      <th className="px-4 pb-2 pt-2 text-right font-medium">Stock</th>
                      <th className="px-4 pb-2 pt-2 text-right font-medium">Demand</th>
                      <th className="px-4 pb-2 pt-2 text-right font-medium">Risk</th>
                    </tr>
                  </thead>
                  <tbody>
                    {overview.data.items.map((item) => (
                      <OverviewRow key={item.part_id} item={item} onSelect={setSelectedPart} />
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState title="No forecast preview" description="Seed the demo dataset first." />
            )}
          </Card>
        </div>

        <div>
          {!selectedPart ? (
            <Card>
              <EmptyState
                icon={PackageCheck}
                title="Select a part"
                description="Pick a high-risk part from the table or search above to see its forecast, interval and drivers."
                action={
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      const first = overview.data?.items[0];
                      if (first) {
                        setSelectedPart({
                          id: first.part_id,
                          part_number: first.part_number,
                          name: first.name,
                        });
                      }
                    }}
                  >
                    Use highest-risk part
                  </Button>
                }
              />
            </Card>
          ) : forecast.isError ? (
            <ErrorState message={(forecast.error as Error).message} />
          ) : forecast.isLoading || !forecast.data ? (
            <div className="space-y-4">
              <Skeleton className="h-56 rounded-xl" />
              <Skeleton className="h-48 rounded-xl" />
            </div>
          ) : (
            <ForecastPanel forecast={forecast.data} />
          )}
        </div>
      </div>
    </div>
  );
}

export default function ForecastPage() {
  return (
    <Suspense fallback={<Skeleton className="h-64 rounded-xl" />}>
      <ForecastWorkspace />
    </Suspense>
  );
}
