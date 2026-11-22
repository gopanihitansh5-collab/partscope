"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  Bot,
  Boxes,
  CircuitBoard,
  GitBranch,
  MapPin,
  TrendingUp,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { getPart, rankCompatibilities, type RankedCandidate } from "@/lib/api";
import { formatCurrency, formatDate, formatNumber, formatPercent } from "@/lib/utils";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorState,
  PageHeader,
  ProgressBar,
  Skeleton,
} from "@/components/ui";

function criticalityTone(criticality: string) {
  switch (criticality.toLowerCase()) {
    case "critical":
      return "danger" as const;
    case "high":
      return "warning" as const;
    case "medium":
      return "info" as const;
    default:
      return "neutral" as const;
  }
}

function CandidateCard({ candidate }: { candidate: RankedCandidate }) {
  return (
    <div className="border-t border-ink-100 px-5 py-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <Link
            href={`/parts/${candidate.part_id}`}
            className="font-mono text-xs font-medium text-ink-900 hover:text-accent-600"
          >
            {candidate.part_number}
          </Link>
          <p className="text-sm text-ink-700">{candidate.name}</p>
          <p className="mt-0.5 text-[11px] text-ink-400">
            {candidate.category ?? "Uncategorised"} · {candidate.relationship.replace(/_/g, " ")} ·{" "}
            {candidate.source.replace(/_/g, " ")}
          </p>
        </div>
        <div className="text-right">
          <p className="text-sm font-semibold tabular-nums text-ink-900">{candidate.score.toFixed(2)}</p>
          <p className="text-[10px] uppercase tracking-wide text-ink-400">score</p>
        </div>
      </div>
      <div className="mt-2">
        <ProgressBar value={candidate.score} />
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <Badge tone="neutral">conf {formatPercent(candidate.confidence, 0)}</Badge>
        {candidate.evidence.length > 0 ? (
          <Badge tone="info">
            <GitBranch className="h-3 w-3" /> {candidate.evidence.length} graph hop
            {candidate.evidence.length === 1 ? "" : "s"}
          </Badge>
        ) : null}
        {candidate.warnings.map((warning) => (
          <Badge key={warning} tone="warning">
            {warning}
          </Badge>
        ))}
      </div>
    </div>
  );
}

export default function PartDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);

  const part = useQuery({ queryKey: ["part", id], queryFn: () => getPart(id), enabled: Number.isFinite(id) });
  const compat = useQuery({
    queryKey: ["compat", id],
    queryFn: () => rankCompatibilities(id, 6),
    enabled: Number.isFinite(id),
  });

  if (part.isError) {
    return (
      <div className="space-y-4">
        <Link href="/search" className="inline-flex items-center gap-1 text-xs text-ink-500 hover:text-ink-800">
          <ArrowLeft className="h-3 w-3" /> Back to catalog
        </Link>
        <ErrorState message={(part.error as Error).message} />
      </div>
    );
  }

  if (part.isLoading || !part.data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-24 rounded-xl" />
        <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
          <Skeleton className="h-72 rounded-xl" />
          <Skeleton className="h-72 rounded-xl" />
        </div>
      </div>
    );
  }

  const data = part.data;
  const totalStock = data.inventory.reduce((sum, row) => sum + row.quantity, 0);

  return (
    <div className="space-y-5">
      <Link href="/search" className="inline-flex items-center gap-1 text-xs text-ink-500 hover:text-ink-800">
        <ArrowLeft className="h-3 w-3" /> Back to catalog
      </Link>

      <PageHeader
        eyebrow={`${data.category?.name ?? "Catalog"} · ${data.manufacturer?.name ?? "Unknown manufacturer"}`}
        title={data.name}
        description={data.description ?? undefined}
        actions={
          <>
            <Link href={`/forecast?part=${data.id}`}>
              <Button variant="outline">
                <TrendingUp className="h-4 w-4" /> Forecast
              </Button>
            </Link>
            <Link
              href={`/chat?part_id=${data.id}&q=${encodeURIComponent(
                `Assess ${data.part_number} and suggest compatible replacements`,
              )}`}
            >
              <Button variant="accent">
                <Bot className="h-4 w-4" /> Ask assistant
              </Button>
            </Link>
          </>
        }
      />

      <Card className="flex flex-wrap items-center gap-x-6 gap-y-3 px-5 py-4">
        <div>
          <p className="text-[10px] uppercase tracking-wide text-ink-400">Part number</p>
          <p className="font-mono text-sm font-medium text-ink-900">{data.part_number}</p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wide text-ink-400">Status</p>
          <Badge tone={data.status === "active" ? "success" : data.status === "superseded" ? "warning" : "neutral"}>
            {data.status}
          </Badge>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wide text-ink-400">Criticality</p>
          <Badge tone={criticalityTone(data.criticality)}>{data.criticality}</Badge>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wide text-ink-400">Unit price</p>
          <p className="text-sm font-medium tabular-nums text-ink-900">
            {formatCurrency(data.price, data.currency)}
          </p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wide text-ink-400">On hand</p>
          <p className="text-sm font-medium tabular-nums text-ink-900">{formatNumber(totalStock)}</p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wide text-ink-400">Equipment fit</p>
          <p className="text-sm font-medium text-ink-900">{data.equipment_models.length}</p>
        </div>
        {data.is_synthetic ? <Badge tone="accent">synthetic</Badge> : null}
      </Card>

      <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
        <div className="space-y-4">
          <Card>
            <CardHeader
              icon={CircuitBoard}
              title="Specifications"
              description={`${data.specifications.length} structured attributes`}
            />
            {data.specifications.length === 0 ? (
              <EmptyState title="No specifications recorded" />
            ) : (
              <dl className="grid gap-x-6 gap-y-3 px-5 py-4 sm:grid-cols-2">
                {data.specifications.map((spec) => (
                  <div key={spec.id} className="flex items-baseline justify-between gap-3 border-b border-dashed border-ink-100 pb-2">
                    <dt className="text-xs text-ink-500">{spec.name}</dt>
                    <dd className="text-right text-xs font-medium text-ink-900">
                      {spec.value}
                      {spec.unit ? <span className="ml-1 text-ink-400">{spec.unit}</span> : null}
                    </dd>
                  </div>
                ))}
              </dl>
            )}
          </Card>

          <Card>
            <CardHeader
              icon={MapPin}
              title="Inventory by location"
              description={`${data.inventory.length} snapshots · ${formatNumber(totalStock)} units on hand`}
            />
            {data.inventory.length === 0 ? (
              <EmptyState title="No inventory snapshots" />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead>
                    <tr className="text-[10px] uppercase tracking-wider text-ink-400">
                      <th className="px-5 pb-2 pt-3 font-medium">Location</th>
                      <th className="px-5 pb-2 pt-3 font-medium">Region</th>
                      <th className="px-5 pb-2 pt-3 text-right font-medium">Quantity</th>
                      <th className="px-5 pb-2 pt-3 text-right font-medium">Snapshot</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.inventory.map((row, index) => (
                      <tr key={`${row.location}-${index}`} className="border-t border-ink-100">
                        <td className="px-5 py-2.5 text-xs text-ink-800">{row.location}</td>
                        <td className="px-5 py-2.5 text-xs text-ink-500">{row.region}</td>
                        <td className="px-5 py-2.5 text-right text-xs tabular-nums text-ink-800">
                          {formatNumber(row.quantity)}
                        </td>
                        <td className="px-5 py-2.5 text-right text-xs text-ink-400">{formatDate(row.snapshot_date)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <Card>
            <CardHeader
              icon={Boxes}
              title="Fits equipment"
              description="Equipment models linked through compatibility evidence"
            />
            {data.equipment_models.length === 0 ? (
              <EmptyState title="No equipment links" />
            ) : (
              <div className="flex flex-wrap gap-2 px-5 py-4">
                {data.equipment_models.map((equipment) => (
                  <span
                    key={equipment.id}
                    className="rounded-lg border border-ink-200 bg-ink-50 px-3 py-1.5 text-xs text-ink-700"
                  >
                    {equipment.name}
                    <span className="ml-2 text-[10px] uppercase tracking-wide text-ink-400">{equipment.kind}</span>
                  </span>
                ))}
              </div>
            )}
          </Card>
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader
              icon={GitBranch}
              title="Ranked compatibility"
              description={
                compat.data
                  ? `${compat.data.candidates.length} candidates · ${compat.data.graph_nodes} nodes / ${compat.data.graph_edges} edges`
                  : "Graph traversal with spec and equipment signals"
              }
            />
            {compat.isError ? (
              <div className="p-5">
                <ErrorState message={(compat.error as Error).message} />
              </div>
            ) : compat.isLoading ? (
              <div className="space-y-3 p-5">
                {Array.from({ length: 4 }).map((_, index) => (
                  <Skeleton key={index} className="h-16" />
                ))}
              </div>
            ) : compat.data && compat.data.candidates.length > 0 ? (
              <div>
                {compat.data.candidates.map((candidate) => (
                  <CandidateCard key={candidate.part_id} candidate={candidate} />
                ))}
              </div>
            ) : (
              <EmptyState
                title="No compatibility evidence"
                description="This part has no linked alternatives in the graph yet."
              />
            )}
          </Card>

          {data.superseded_by ? (
            <Card className="p-5">
              <p className="text-[10px] uppercase tracking-wide text-ink-400">Superseded by</p>
              <Link
                href={`/parts/${data.superseded_by.id}`}
                className="mt-1 block text-sm font-medium text-accent-600 hover:text-accent-700"
              >
                {data.superseded_by.part_number} — {data.superseded_by.name}
              </Link>
            </Card>
          ) : null}

          <Card className="p-5">
            <p className="text-xs font-semibold text-ink-900">Need a decision?</p>
            <p className="mt-1 text-xs leading-relaxed text-ink-500">
              Run the assistant to combine compatibility, documentation and stock risk into one
              evidence-backed recommendation.
            </p>
            <Link href={`/chat?part_id=${data.id}`} className="mt-3 inline-block">
              <Button size="sm" variant="primary">
                <Bot className="h-3.5 w-3.5" /> Open assistant
              </Button>
            </Link>
          </Card>
        </div>
      </div>
    </div>
  );
}
