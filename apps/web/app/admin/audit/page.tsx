"use client";

import { useQuery } from "@tanstack/react-query";
import { Search, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { getAudit } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";
import {
  Badge,
  Card,
  CardHeader,
  EmptyState,
  ErrorState,
  Input,
  PageHeader,
  Skeleton,
} from "@/components/ui";

export default function AuditPage() {
  const [action, setAction] = useState("");
  const audit = useQuery({ queryKey: ["audit", 150], queryFn: () => getAudit(150) });

  const rows = (audit.data ?? []).filter((event) =>
    action ? event.action.toLowerCase().includes(action.toLowerCase()) : true,
  );

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Admin"
        title="Audit trail"
        description="Catalog mutations, imports, model registrations and agent runs are written to an append-only event log."
        actions={
          <Badge tone="success">
            <ShieldCheck className="h-3 w-3" /> append-only
          </Badge>
        }
      />

      <Card className="p-4">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
          <Input
            value={action}
            onChange={(event) => setAction(event.target.value)}
            placeholder="Filter by action — e.g. part.import, part.update, agent.run"
            className="pl-9"
          />
        </div>
      </Card>

      {audit.isError ? <ErrorState message={(audit.error as Error).message} /> : null}

      <Card>
        <CardHeader
          icon={ShieldCheck}
          title="Events"
          description={audit.data ? `${rows.length} of ${audit.data.length} events` : "Loading events…"}
        />
        {audit.isLoading ? (
          <div className="space-y-2 p-5">
            {Array.from({ length: 8 }).map((_, index) => (
              <Skeleton key={index} className="h-9" />
            ))}
          </div>
        ) : rows.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="text-[10px] uppercase tracking-wider text-ink-400">
                  <th className="px-5 pb-2 font-medium">When</th>
                  <th className="px-5 pb-2 font-medium">Actor</th>
                  <th className="px-5 pb-2 font-medium">Action</th>
                  <th className="px-5 pb-2 font-medium">Entity</th>
                  <th className="px-5 pb-2 font-medium">Payload</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((event) => (
                  <tr key={event.id} className="border-t border-ink-100">
                    <td className="whitespace-nowrap px-5 py-2.5 text-[11px] text-ink-500">
                      {formatDateTime(event.created_at)}
                    </td>
                    <td className="px-5 py-2.5 text-[11px] text-ink-600">{event.actor}</td>
                    <td className="px-5 py-2.5">
                      <span className="rounded bg-ink-100 px-1.5 py-0.5 font-mono text-[10px] text-ink-700">
                        {event.action}
                      </span>
                    </td>
                    <td className="px-5 py-2.5 text-[11px] text-ink-500">
                      {event.entity_type}
                      {event.entity_id ? ` · ${event.entity_id}` : ""}
                    </td>
                    <td className="max-w-md truncate px-5 py-2.5 font-mono text-[10px] text-ink-400">
                      {JSON.stringify(event.payload)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            icon={ShieldCheck}
            title="No audit events"
            description="Events appear after catalog edits, imports, training and agent runs."
          />
        )}
      </Card>
    </div>
  );
}
