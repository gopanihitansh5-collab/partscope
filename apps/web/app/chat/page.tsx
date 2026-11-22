"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  Bot,
  CheckCircle2,
  CircleDashed,
  FileText,
  GitBranch,
  Loader2,
  Search,
  Send,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  X,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import {
  getPart,
  getRun,
  runAgent,
  searchParts,
  sendFeedback,
  type AgentAlternative,
  type AgentRun,
  type Citation,
  type TraceEvent,
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
  ProgressBar,
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

function Citations({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;
  return (
    <div className="mt-3 space-y-1.5">
      {citations.map((citation) => (
        <div
          key={`${citation.chunk_id}-${citation.page}`}
          className="flex items-start gap-2 rounded-md border border-ink-100 bg-ink-50/70 px-2.5 py-1.5"
        >
          <FileText className="mt-0.5 h-3 w-3 shrink-0 text-ink-400" />
          <div className="min-w-0">
            <p className="truncate text-[11px] font-medium text-ink-700">{citation.document_title}</p>
            <p className="text-[10px] text-ink-400">
              p.{citation.page}
              {citation.section ? ` · ${citation.section}` : ""} · score {citation.score.toFixed(2)}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}

function AlternativeCard({ alternative, rank }: { alternative: AgentAlternative; rank: number }) {
  return (
    <div className="rounded-lg border border-ink-200 bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-5 w-5 items-center justify-center rounded bg-ink-950 text-[10px] font-semibold text-white">
              {rank}
            </span>
            <Link
              href={`/parts/${alternative.part_id}`}
              className="font-mono text-xs font-medium text-ink-900 hover:text-accent-600"
            >
              {alternative.part_number}
            </Link>
            <Badge tone={alternative.evidence_complete ? "success" : "warning"}>
              {alternative.evidence_complete ? "complete" : "partial"}
            </Badge>
          </div>
          <p className="mt-1 text-sm text-ink-700">{alternative.name}</p>
          <p className="mt-0.5 text-[11px] text-ink-400">
            {alternative.category ?? "Uncategorised"} · {alternative.relationship.replace(/_/g, " ")} ·{" "}
            {alternative.source.replace(/_/g, " ")}
          </p>
        </div>
        <div className="text-right">
          <p className="text-sm font-semibold tabular-nums text-ink-900">{alternative.score.toFixed(2)}</p>
          <p className="text-[10px] uppercase tracking-wide text-ink-400">score</p>
        </div>
      </div>

      <div className="mt-2">
        <ProgressBar value={alternative.score} />
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Badge tone="neutral">conf {formatPercent(alternative.confidence, 0)}</Badge>
        {alternative.forecast ? (
          <>
            <Badge tone={riskTone(alternative.forecast.risk_level)}>
              {alternative.forecast.risk_level} risk
            </Badge>
            <Badge tone="info">
              30d demand {formatNumber(alternative.forecast.expected_demand, 1)}
            </Badge>
          </>
        ) : null}
        {alternative.evidence_path.length > 0 ? (
          <Badge tone="info">
            <GitBranch className="h-3 w-3" /> {alternative.evidence_path.length} hops
          </Badge>
        ) : null}
      </div>

      {alternative.evidence_path.length > 0 ? (
        <div className="mt-3 flex flex-wrap items-center gap-1 text-[10px] text-ink-500">
          {alternative.evidence_path.map((step, index) => (
            <span key={`${step.part_id}-${index}`} className="flex items-center gap-1">
              {index > 0 ? <ArrowRight className="h-3 w-3 text-ink-300" /> : null}
              <span className="rounded bg-ink-100 px-1.5 py-0.5 font-mono">{step.part_number}</span>
            </span>
          ))}
        </div>
      ) : null}

      <Citations citations={alternative.citations} />

      {alternative.warnings.length > 0 ? (
        <div className="mt-2 space-y-0.5">
          {alternative.warnings.map((warning) => (
            <p key={warning} className="flex items-start gap-1.5 text-[10px] text-amber-700">
              <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" /> {warning}
            </p>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function TraceTimeline({ trace }: { trace: TraceEvent[] }) {
  if (trace.length === 0) return null;
  return (
    <ol className="space-y-0">
      {trace.map((event, index) => {
        const ok = ["ok", "completed", "success"].includes(event.status.toLowerCase());
        const failed = ["error", "failed"].includes(event.status.toLowerCase());
        return (
          <li key={`${event.node}-${index}`} className="relative flex gap-3 pb-3 last:pb-0">
            {index < trace.length - 1 ? (
              <span className="absolute left-[7px] top-4 h-full w-px bg-ink-200" />
            ) : null}
            <span
              className={cn(
                "relative mt-1 flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full ring-4 ring-white",
                failed ? "bg-rose-500" : ok ? "bg-emerald-500" : "bg-ink-300",
              )}
            />
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs font-medium text-ink-800">{titleCase(event.node)}</p>
                {event.latency_ms ? (
                  <span className="text-[10px] tabular-nums text-ink-400">{Math.round(event.latency_ms)} ms</span>
                ) : null}
              </div>
              <p className="text-[10px] text-ink-400">
                {event.status}
                {event.detail ? ` · ${event.detail}` : ""}
              </p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function RunView({ run }: { run: AgentRun }) {
  const [feedback, setFeedback] = useState<string | null>(null);
  const feedbackMutation = useMutation({
    mutationFn: ({ rating }: { rating: number }) => sendFeedback(run.run_id, rating),
    onSuccess: (_data, variables) =>
      setFeedback(variables.rating > 0 ? "Marked helpful" : "Feedback recorded"),
  });

  const response = run.response;

  return (
    <div className="space-y-4">
      <Card className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={run.status === "completed" ? "success" : run.status === "failed" ? "danger" : "info"}>
                {run.status}
              </Badge>
              {run.intent ? <Badge tone="accent">{titleCase(run.intent)}</Badge> : null}
              {response ? (
                <Badge tone={response.evidence_complete ? "success" : "warning"}>
                  {response.evidence_complete ? "evidence complete" : "evidence gaps"}
                </Badge>
              ) : null}
              <span className="text-[11px] text-ink-400">{formatDateTime(run.created_at)}</span>
              {run.latency_ms ? (
                <span className="text-[11px] text-ink-400">· {Math.round(run.latency_ms)} ms</span>
              ) : null}
            </div>
            <h2 className="mt-2 text-base font-semibold text-ink-900">{run.query}</h2>
          </div>
          <div className="flex items-center gap-1">
            <Button
              size="sm"
              variant="ghost"
              aria-label="Helpful"
              onClick={() => feedbackMutation.mutate({ rating: 1 })}
            >
              <ThumbsUp className="h-3.5 w-3.5" />
            </Button>
            <Button
              size="sm"
              variant="ghost"
              aria-label="Not helpful"
              onClick={() => feedbackMutation.mutate({ rating: -1 })}
            >
              <ThumbsDown className="h-3.5 w-3.5" />
            </Button>
            {feedback ? <span className="text-[11px] text-ink-400">{feedback}</span> : null}
          </div>
        </div>

        {run.error ? (
          <div className="mt-3">
            <ErrorState message={run.error} />
          </div>
        ) : null}

        {response ? (
          <div className="mt-4 space-y-4">
            <div className="rounded-lg bg-ink-950 p-4 text-sm leading-relaxed text-ink-100">
              <p className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wide text-accent-400">
                <Sparkles className="h-3 w-3" /> Recommendation
              </p>
              <p className="mt-2">{response.summary}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                <Badge tone="neutral" className="bg-white/10 text-ink-200 ring-white/10">
                  confidence {formatPercent(response.confidence, 0)}
                </Badge>
                {response.insufficient_evidence ? (
                  <Badge tone="warning">insufficient evidence</Badge>
                ) : null}
                {response.source_part ? (
                  <Badge tone="info">
                    source {response.source_part.part_number}
                  </Badge>
                ) : null}
              </div>
            </div>

            {response.plan.length > 0 ? (
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wide text-ink-400">Plan</p>
                <ol className="mt-1.5 grid gap-1.5 sm:grid-cols-2">
                  {response.plan.map((step, index) => (
                    <li key={`${step}-${index}`} className="flex items-start gap-2 text-xs text-ink-600">
                      <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-ink-100 text-[9px] font-semibold text-ink-500">
                        {index + 1}
                      </span>
                      {step}
                    </li>
                  ))}
                </ol>
              </div>
            ) : null}

            {response.alternatives.length > 0 ? (
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wide text-ink-400">
                  Ranked alternatives
                </p>
                <div className="mt-2 grid gap-2">
                  {response.alternatives.map((alternative, index) => (
                    <AlternativeCard key={alternative.part_id} alternative={alternative} rank={index + 1} />
                  ))}
                </div>
              </div>
            ) : null}

            {response.documentation.answer ? (
              <div className="rounded-lg border border-ink-200 p-4">
                <p className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wide text-ink-400">
                  <FileText className="h-3 w-3" /> Documentation
                </p>
                <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-ink-700">
                  {response.documentation.answer}
                </p>
                <Citations citations={response.documentation.citations} />
                {!response.documentation.grounded ? (
                  <p className="mt-2 text-[11px] text-amber-600">
                    Answer is not fully grounded in retrieved text.
                  </p>
                ) : null}
              </div>
            ) : null}

            {response.warnings.length > 0 ? (
              <div className="space-y-1 rounded-lg bg-amber-50 px-3 py-2">
                {response.warnings.map((warning) => (
                  <p key={warning} className="flex items-start gap-2 text-[11px] text-amber-700">
                    <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" /> {warning}
                  </p>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
      </Card>

      <Card>
        <CardHeader icon={CircleDashed} title="Execution trace" description="Every node and tool call is persisted" />
        <div className="px-5 py-4">
          <TraceTimeline trace={run.trace} />
          {run.trace.length === 0 ? <EmptyState title="No trace events" /> : null}
        </div>
      </Card>
    </div>
  );
}

function AssistantWorkspace() {
  const searchParams = useSearchParams();
  const initialQuery = searchParams.get("q") ?? "";
  const runParam = searchParams.get("run");
  const partParam = searchParams.get("part_id");

  const [query, setQuery] = useState(initialQuery);
  const [selectedPart, setSelectedPart] = useState<PartRef | null>(null);
  const [partQuery, setPartQuery] = useState("");
  const [showPicker, setShowPicker] = useState(false);
  const [includeForecast, setIncludeForecast] = useState(true);
  const [includeRetrieval, setIncludeRetrieval] = useState(true);
  const [includeCompatibility, setIncludeCompatibility] = useState(true);

  const debouncedPartQuery = useDebounced(partQuery);
  const partResults = useQuery({
    queryKey: ["part-picker", debouncedPartQuery],
    queryFn: () => searchParts({ query: debouncedPartQuery, limit: 6 }),
    enabled: debouncedPartQuery.length >= 2,
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

  const existing = useQuery({
    queryKey: ["run", runParam],
    queryFn: () => getRun(runParam as string),
    enabled: Boolean(runParam),
  });

  const mutation = useMutation({
    mutationFn: () =>
      runAgent({
        query: query.trim(),
        part_id: selectedPart?.id ?? null,
        include_forecast: includeForecast,
        include_retrieval: includeRetrieval,
        include_compatibility: includeCompatibility,
      }),
  });

  const autoRan = useRef(false);
  useEffect(() => {
    if (!autoRan.current && initialQuery && !runParam) {
      autoRan.current = true;
      mutation.mutate();
    }
  }, [initialQuery, runParam, mutation]);

  function submit() {
    if (!query.trim() || mutation.isPending) return;
    mutation.mutate();
  }

  const activeRun = mutation.data ?? existing.data;

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Assistant"
        title="Ask across catalog, documents and stock"
        description="The workflow plans its own tool calls, ranks compatibility with graph evidence, cites documentation pages and checks shortage risk."
        actions={
          <Badge tone="accent">
            <Bot className="h-3 w-3" /> LangGraph workflow
          </Badge>
        }
      />

      <Card className="p-5">
        <div className="space-y-3">
          <div className="flex flex-col gap-2 sm:flex-row">
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") submit();
              }}
              placeholder="e.g. compatible replacement for BRG1000 and stock risk next month"
              className="h-11 flex-1"
            />
            <Button variant="accent" className="h-11 shrink-0" onClick={submit} loading={mutation.isPending}>
              <Send className="h-4 w-4" /> Run
            </Button>
          </div>

          <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
            <div className="relative flex-1">
              {selectedPart ? (
                <div className="flex items-center gap-2 rounded-lg border border-accent-200 bg-accent-50 px-3 py-2 text-xs text-accent-800">
                  <span className="font-mono font-medium">{selectedPart.part_number}</span>
                  <span className="truncate text-accent-700">{selectedPart.name}</span>
                  <button
                    type="button"
                    className="ml-auto text-accent-500 hover:text-accent-700"
                    onClick={() => setSelectedPart(null)}
                    aria-label="Clear part"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              ) : (
                <>
                  <div className="relative">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
                    <Input
                      value={partQuery}
                      onChange={(event) => {
                        setPartQuery(event.target.value);
                        setShowPicker(true);
                      }}
                      onFocus={() => setShowPicker(true)}
                      placeholder="Attach a part (optional) — search by number or name"
                      className="pl-9"
                    />
                  </div>
                  {showPicker && debouncedPartQuery.length >= 2 ? (
                    <div className="absolute z-20 mt-1 w-full overflow-hidden rounded-lg border border-ink-200 bg-white shadow-lg">
                      {partResults.isLoading ? (
                        <p className="px-3 py-2 text-xs text-ink-400">Searching…</p>
                      ) : partResults.data && partResults.data.items.length > 0 ? (
                        partResults.data.items.map((part) => (
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
                        <p className="px-3 py-2 text-xs text-ink-400">No matches</p>
                      )}
                    </div>
                  ) : null}
                </>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {[
                { label: "Compatibility", value: includeCompatibility, set: setIncludeCompatibility },
                { label: "Documents", value: includeRetrieval, set: setIncludeRetrieval },
                { label: "Forecast", value: includeForecast, set: setIncludeForecast },
              ].map((toggle) => (
                <button
                  key={toggle.label}
                  type="button"
                  onClick={() => toggle.set(!toggle.value)}
                  className={cn(
                    "rounded-full border px-3 py-1.5 text-[11px] font-medium transition-colors",
                    toggle.value
                      ? "border-accent-300 bg-accent-50 text-accent-700"
                      : "border-ink-200 bg-white text-ink-400",
                  )}
                >
                  {toggle.value ? <CheckCircle2 className="mr-1 inline h-3 w-3" /> : null}
                  {toggle.label}
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            {[
              "Find a compatible replacement and check stock",
              "What do the docs say about installation torque?",
              "Which alternatives are superseded and why?",
            ].map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => setQuery(example)}
                className="rounded-full bg-ink-100 px-3 py-1 text-[11px] text-ink-600 hover:bg-ink-200"
              >
                {example}
              </button>
            ))}
          </div>
        </div>
      </Card>

      {mutation.isError ? <ErrorState message={(mutation.error as Error).message} /> : null}
      {existing.isError ? <ErrorState message={(existing.error as Error).message} /> : null}

      {mutation.isPending ? (
        <Card className="flex flex-col items-center gap-3 px-5 py-14">
          <Loader2 className="h-6 w-6 animate-spin text-accent-500" />
          <p className="text-sm text-ink-600">Planning and executing tool calls…</p>
          <p className="text-xs text-ink-400">Graph traversal, retrieval and forecasting run in sequence.</p>
        </Card>
      ) : existing.isLoading ? (
        <Skeleton className="h-64 rounded-xl" />
      ) : activeRun ? (
        <RunView run={activeRun} />
      ) : (
        <Card>
          <EmptyState
            icon={Bot}
            title="No run yet"
            description="Ask a question above, optionally attach a part, and the assistant will assemble an evidence-backed answer."
          />
        </Card>
      )}
    </div>
  );
}

export default function AssistantPage() {
  return (
    <Suspense fallback={<Skeleton className="h-64 rounded-xl" />}>
      <AssistantWorkspace />
    </Suspense>
  );
}
