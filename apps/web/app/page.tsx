"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Bot,
  Boxes,
  FileText,
  GitBranch,
  Search,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import {
  getAdminStats,
  getForecastOverview,
  listDocuments,
  listRuns,
  type AgentRun,
  type OverviewItem,
} from "@/lib/api";
import { cn, formatDateTime, formatNumber, formatPercent, riskTone, titleCase } from "@/lib/utils";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorState,
  Input,
  PageHeader,
  Skeleton,
  Stat,
} from "@/components/ui";

const EXAMPLES = [
  "Find a compatible replacement for a failed ball bearing",
  "Which conveyor belts are at stock risk next month?",
  "What does the manual say about V-belt tensioning?",
];

function RiskRow({ item }: { item: OverviewItem }) {
  return (
    <tr className="border-t border-ink-100">
      <td className="px-5 py-3">
        <Link href={`/parts/${item.part_id}`} className="font-mono text-xs text-ink-900 hover:text-accent-600">
          {item.part_number}
        </Link>
        <p className="text-xs text-ink-500">{item.name}</p>
      </td>
      <td className="px-5 py-3 text-xs text-ink-500">{item.category ?? "—"}</td>
      <td className="px-5 py-3 text-right text-xs tabular-nums text-ink-700">
        {formatNumber(item.current_stock)}
      </td>
      <td className="px-5 py-3 text-right text-xs tabular-nums text-ink-700">
        {formatNumber(item.expected_30d_demand, 1)}
      </td>
      <td className="px-5 py-3 text-right">
        <Badge tone={riskTone(item.risk_level)}>{formatPercent(item.shortage_risk, 0)}</Badge>
      </td>
    </tr>
  );
}

function RunRow({ run }: { run: AgentRun }) {
  return (
    <Link
      href={`/chat?run=${run.run_id}`}
      className="flex items-start justify-between gap-3 border-t border-ink-100 px-5 py-3 transition-colors hover:bg-ink-50"
    >
      <div className="min-w-0">
        <p className="truncate text-sm text-ink-800">{run.query}</p>
        <p className="mt-0.5 text-[11px] text-ink-400">
          {formatDateTime(run.created_at)} · {run.intent ? titleCase(run.intent) : "routing"} ·{" "}
          {run.latency_ms ? `${Math.round(run.latency_ms)} ms` : "pending"}
        </p>
      </div>
      <Badge tone={run.status === "completed" ? "success" : run.status === "failed" ? "danger" : "info"}>
        {run.status}
      </Badge>
    </Link>
  );
}

export default function OverviewPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");

  const stats = useQuery({ queryKey: ["admin-stats"], queryFn: getAdminStats });
  const overview = useQuery({ queryKey: ["forecast-overview", 8], queryFn: () => getForecastOverview(8) });
  const runs = useQuery({ queryKey: ["runs", 6], queryFn: () => listRuns(6) });
  const documents = useQuery({ queryKey: ["documents"], queryFn: () => listDocuments() });

  const highRisk = overview.data?.items.filter((item) =>
    ["high", "critical"].includes(item.risk_level.toLowerCase()),
  ).length;

  function submit() {
    const value = query.trim();
    router.push(value ? `/chat?q=${encodeURIComponent(value)}` : "/chat");
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Operations overview"
        title="Parts intelligence, grounded in evidence"
        description="One workspace for identification, compatibility, documentation and demand risk across the spare-parts catalog."
        actions={
          <>
            <Link href="/search">
              <Button variant="outline">
                <Search className="h-4 w-4" /> Browse catalog
              </Button>
            </Link>
            <Link href="/chat">
              <Button variant="accent">
                <Bot className="h-4 w-4" /> Open assistant
              </Button>
            </Link>
          </>
        }
      />

      <section className="grid-pattern overflow-hidden rounded-2xl bg-ink-950 p-6 text-white sm:p-8">
        <div className="max-w-3xl">
          <Badge tone="accent" className="bg-accent-500/15 text-accent-300 ring-accent-400/30">
            <Sparkles className="h-3 w-3" /> Agentic workflow
          </Badge>
          <h2 className="mt-4 text-xl font-semibold tracking-tight sm:text-2xl">
            Ask one question across images, specs, documents and stock.
          </h2>
          <p className="mt-2 text-sm text-ink-300">
            The assistant plans tool calls, ranks compatibility with graph evidence, cites document
            pages and forecasts shortage risk before answering.
          </p>
          <form
            className="mt-5 flex flex-col gap-2 sm:flex-row"
            onSubmit={(event) => {
              event.preventDefault();
              submit();
            }}
          >
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="e.g. replacement for bearing BRG1000 on line 2, stock risk next month"
              className="h-11 border-white/15 bg-white/10 text-white placeholder:text-ink-400 focus:border-accent-400 focus:ring-accent-500/20"
            />
            <Button type="submit" variant="accent" className="h-11 shrink-0">
              Run assistant <ArrowRight className="h-4 w-4" />
            </Button>
          </form>
          <div className="mt-3 flex flex-wrap gap-2">
            {EXAMPLES.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => router.push(`/chat?q=${encodeURIComponent(example)}`)}
                className="rounded-full border border-white/10 px-3 py-1 text-[11px] text-ink-300 transition-colors hover:border-accent-400/40 hover:text-white"
              >
                {example}
              </button>
            ))}
          </div>
        </div>
      </section>

      {stats.isError ? <ErrorState message={(stats.error as Error).message} /> : null}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {stats.isLoading ? (
          Array.from({ length: 4 }).map((_, index) => <Skeleton key={index} className="h-[104px] rounded-xl" />)
        ) : (
          <>
            <Stat
              label="Catalog parts"
              value={formatNumber(stats.data?.catalog.parts ?? 0)}
              hint={`${formatNumber(stats.data?.catalog.categories ?? 0)} categories · ${formatNumber(
                stats.data?.catalog.manufacturers ?? 0,
              )} manufacturers`}
              icon={Boxes}
              tone="accent"
            />
            <Stat
              label="Compatibility links"
              value={formatNumber(stats.data?.catalog.compatibilities ?? 0)}
              hint={`${formatNumber(stats.data?.graph.edges.part_supplier ?? 0)} supplier edges`}
              icon={GitBranch}
            />
            <Stat
              label="Knowledge documents"
              value={formatNumber(documents.data?.length ?? 0)}
              hint="Manuals, bulletins and spec sheets"
              icon={FileText}
            />
            <Stat
              label="High-risk parts"
              value={formatNumber(highRisk ?? 0)}
              hint="Projected stockout within 30 days"
              icon={TrendingUp}
              tone="warning"
            />
          </>
        )}
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader
            icon={TrendingUp}
            title="Stock risk preview"
            description={
              overview.data
                ? `${overview.data.method} · as of ${overview.data.as_of}`
                : "Last-30-day demand vs latest stock"
            }
            action={
              <Link href="/forecast" className="text-xs font-medium text-accent-600 hover:text-accent-700">
                Full forecast →
              </Link>
            }
          />
          {overview.isError ? (
            <div className="p-5">
              <ErrorState message={(overview.error as Error).message} />
            </div>
          ) : overview.isLoading ? (
            <div className="space-y-2 p-5">
              {Array.from({ length: 5 }).map((_, index) => (
                <Skeleton key={index} className="h-9" />
              ))}
            </div>
          ) : overview.data && overview.data.items.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="text-[10px] uppercase tracking-wider text-ink-400">
                    <th className="px-5 pb-2 pt-3 font-medium">Part</th>
                    <th className="px-5 pb-2 pt-3 font-medium">Category</th>
                    <th className="px-5 pb-2 pt-3 text-right font-medium">Stock</th>
                    <th className="px-5 pb-2 pt-3 text-right font-medium">30d demand</th>
                    <th className="px-5 pb-2 pt-3 text-right font-medium">Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {overview.data.items.slice(0, 8).map((item) => (
                    <RiskRow key={item.part_id} item={item} />
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState title="No risk preview available" description="Seed the demo dataset first." />
          )}
        </Card>

        <Card>
          <CardHeader
            icon={Bot}
            title="Recent assistant runs"
            description="Persisted with traces and tool outputs"
            action={
              <Link href="/chat" className="text-xs font-medium text-accent-600 hover:text-accent-700">
                New run →
              </Link>
            }
          />
          {runs.isError ? (
            <div className="p-5">
              <ErrorState message={(runs.error as Error).message} />
            </div>
          ) : runs.isLoading ? (
            <div className="space-y-2 p-5">
              {Array.from({ length: 4 }).map((_, index) => (
                <Skeleton key={index} className="h-10" />
              ))}
            </div>
          ) : runs.data && runs.data.length > 0 ? (
            <div>
              {runs.data.map((run) => (
                <RunRow key={run.run_id} run={run} />
              ))}
            </div>
          ) : (
            <EmptyState
              icon={Bot}
              title="No runs yet"
              description="Ask the assistant a question to see traces here."
              action={
                <Link href="/chat">
                  <Button size="sm" variant="outline">
                    Start a run
                  </Button>
                </Link>
              }
            />
          )}
        </Card>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { href: "/search", icon: Search, title: "Catalog search", body: "Fuzzy part lookup with spec, stock and criticality filters." },
          { href: "/identify", icon: Boxes, title: "Vision ID", body: "Upload a photo and get ranked candidates with confidence." },
          { href: "/forecast", icon: TrendingUp, title: "Demand forecast", body: "Quantile bands, shortage probability and reorder quantity." },
          { href: "/documents", icon: FileText, title: "Grounded answers", body: "Extractive answers with page-level citations." },
        ].map((item) => (
          <Link key={item.href} href={item.href}>
            <Card className={cn("h-full p-5 transition-colors hover:border-accent-300 hover:bg-accent-50/40")}>
              <item.icon className="h-5 w-5 text-accent-500" />
              <p className="mt-3 text-sm font-semibold text-ink-900">{item.title}</p>
              <p className="mt-1 text-xs leading-relaxed text-ink-500">{item.body}</p>
            </Card>
          </Link>
        ))}
      </section>
    </div>
  );
}
