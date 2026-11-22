"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ClipboardPaste, Upload, XCircle } from "lucide-react";
import { useState } from "react";

import { getImports, importParts } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorState,
  PageHeader,
  Skeleton,
} from "@/components/ui";

const SAMPLE = JSON.stringify(
  [
    {
      part_number: "IMP-1001",
      name: "Timing Belt 420-5M",
      description: "Imported replacement belt for line 3 conveyors",
      manufacturer: "NordicDrive",
      category: "Belts",
      price: 18.5,
      currency: "EUR",
      status: "active",
    },
  ],
  null,
  2,
);

export default function ImportsPage() {
  const queryClient = useQueryClient();
  const [text, setText] = useState(SAMPLE);
  const [parseError, setParseError] = useState<string | null>(null);

  const history = useQuery({ queryKey: ["imports"], queryFn: getImports });

  const mutation = useMutation({
    mutationFn: importParts,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["imports"] });
      queryClient.invalidateQueries({ queryKey: ["admin-stats"] });
    },
  });

  function submit() {
    setParseError(null);
    let rows: Record<string, unknown>[];
    try {
      const parsed = JSON.parse(text);
      if (!Array.isArray(parsed)) throw new Error("Expected a JSON array of part rows");
      rows = parsed;
    } catch (error) {
      setParseError((error as Error).message);
      return;
    }
    mutation.mutate(rows);
  }

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Admin"
        title="Catalog imports"
        description="Bulk upsert parts from JSON. Rows are validated against known categories and manufacturers, and every run is audited."
      />

      <div className="grid gap-4 xl:grid-cols-[1.2fr_1fr]">
        <Card>
          <CardHeader
            icon={ClipboardPaste}
            title="Paste rows"
            description="Array of objects · max 5,000 rows per request"
            action={
              <Button size="sm" variant="ghost" onClick={() => setText(SAMPLE)}>
                Reset sample
              </Button>
            }
          />
          <div className="space-y-3 p-5">
            <textarea
              value={text}
              onChange={(event) => setText(event.target.value)}
              spellCheck={false}
              rows={16}
              className="w-full resize-y rounded-lg border border-ink-200 bg-ink-950 p-3 font-mono text-[11px] leading-relaxed text-ink-100 focus:border-accent-400 focus:outline-none focus:ring-2 focus:ring-accent-500/20"
            />
            {parseError ? <ErrorState message={parseError} /> : null}
            {mutation.isError ? <ErrorState message={(mutation.error as Error).message} /> : null}
            <div className="flex items-center justify-between">
              <p className="text-[11px] text-ink-400">
                Required: part_number, name. Category and manufacturer must already exist.
              </p>
              <Button variant="accent" loading={mutation.isPending} onClick={submit}>
                <Upload className="h-4 w-4" /> Import rows
              </Button>
            </div>
          </div>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader icon={Upload} title="Last result" description="Validation outcome for this session" />
            <div className="p-5">
              {mutation.data ? (
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <Badge tone="success">
                      <CheckCircle2 className="h-3 w-3" /> {mutation.data.accepted} accepted
                    </Badge>
                    <Badge tone={mutation.data.rejected > 0 ? "danger" : "neutral"}>
                      <XCircle className="h-3 w-3" /> {mutation.data.rejected} rejected
                    </Badge>
                  </div>
                  {mutation.data.errors.length > 0 ? (
                    <div className="max-h-48 space-y-1 overflow-y-auto rounded-lg bg-rose-50 p-3">
                      {mutation.data.errors.map((error, index) => (
                        <p key={index} className="font-mono text-[10px] text-rose-700">
                          {JSON.stringify(error)}
                        </p>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-ink-500">All rows passed validation and were written.</p>
                  )}
                </div>
              ) : (
                <p className="text-xs text-ink-400">Submit an import to see the validation report.</p>
              )}
            </div>
          </Card>

          <Card>
            <CardHeader icon={ClipboardPaste} title="Import history" description="From the audit log" />
            {history.isError ? (
              <div className="p-5">
                <ErrorState message={(history.error as Error).message} />
              </div>
            ) : history.isLoading ? (
              <div className="space-y-2 p-5">
                {Array.from({ length: 4 }).map((_, index) => (
                  <Skeleton key={index} className="h-8" />
                ))}
              </div>
            ) : history.data && history.data.length > 0 ? (
              <div className="divide-y divide-ink-100">
                {history.data.map((event) => {
                  const payload = (event.payload ?? {}) as Record<string, unknown>;
                  return (
                    <div key={String(event.id)} className="flex items-center justify-between px-5 py-2.5">
                      <div>
                        <p className="text-xs text-ink-700">
                          {String(payload.accepted ?? payload.rows ?? "—")} rows accepted
                        </p>
                        <p className="text-[10px] text-ink-400">
                          {String(event.actor)} · {formatDateTime(String(event.created_at))}
                        </p>
                      </div>
                      <Badge tone={Number(payload.rejected ?? 0) > 0 ? "warning" : "success"}>
                        {String(payload.rejected ?? 0)} rejected
                      </Badge>
                    </div>
                  );
                })}
              </div>
            ) : (
              <EmptyState title="No imports yet" description="Bulk imports will appear here." />
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
