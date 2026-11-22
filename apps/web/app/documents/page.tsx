"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BookOpenCheck,
  CheckCircle2,
  FileSearch,
  FileText,
  RefreshCw,
  Search,
  ShieldAlert,
} from "lucide-react";
import { useState } from "react";

import {
  askDocuments,
  indexDocuments,
  listDocuments,
  type AnswerResponse,
} from "@/lib/api";
import { formatDate, formatPercent, titleCase } from "@/lib/utils";
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
} from "@/components/ui";

function AnswerPanel({ answer }: { answer: AnswerResponse }) {
  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-ink-200 bg-white p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={answer.grounded ? "success" : "warning"}>
            {answer.grounded ? (
              <>
                <CheckCircle2 className="h-3 w-3" /> grounded
              </>
            ) : (
              <>
                <ShieldAlert className="h-3 w-3" /> ungrounded
              </>
            )}
          </Badge>
          <Badge tone="neutral">confidence {formatPercent(answer.confidence, 0)}</Badge>
          {answer.insufficient_evidence ? <Badge tone="danger">insufficient evidence</Badge> : null}
          <span className="text-[11px] text-ink-400">{answer.citations.length} citations</span>
        </div>
        <p className="mt-3 whitespace-pre-line text-sm leading-relaxed text-ink-700">{answer.answer}</p>
      </div>

      {answer.citations.length > 0 ? (
        <Card>
          <CardHeader icon={FileText} title="Citations" description="Page-level provenance" />
          <div className="divide-y divide-ink-100">
            {answer.citations.map((citation) => (
              <div key={`${citation.chunk_id}`} className="px-5 py-2.5">
                <p className="text-xs font-medium text-ink-800">{citation.document_title}</p>
                <p className="text-[11px] text-ink-400">
                  p.{citation.page}
                  {citation.section ? ` · ${citation.section}` : ""} · chunk {citation.chunk_id} · score{" "}
                  {citation.score.toFixed(2)}
                </p>
              </div>
            ))}
          </div>
        </Card>
      ) : null}

      {answer.chunks.length > 0 ? (
        <Card>
          <CardHeader
            icon={BookOpenCheck}
            title="Retrieved context"
            description="Hybrid lexical + entity + graph ranking"
          />
          <div className="divide-y divide-ink-100">
            {answer.chunks.map((chunk) => (
              <details key={chunk.chunk_id} className="group px-5 py-3">
                <summary className="cursor-pointer list-none">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-xs font-medium text-ink-700">
                      {chunk.document_title} · p.{chunk.page}
                    </span>
                    <span className="text-[10px] tabular-nums text-ink-400">
                      {chunk.score.toFixed(3)}
                    </span>
                  </div>
                  <p className="mt-1 line-clamp-2 text-[11px] text-ink-400 group-open:hidden">
                    {chunk.text}
                  </p>
                </summary>
                <p className="mt-2 whitespace-pre-line text-xs leading-relaxed text-ink-600">
                  {chunk.text}
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5 text-[10px] text-ink-400">
                  <span className="rounded bg-ink-100 px-1.5 py-0.5">lexical {chunk.vector_score.toFixed(2)}</span>
                  <span className="rounded bg-ink-100 px-1.5 py-0.5">entity {chunk.entity_score.toFixed(2)}</span>
                  <span className="rounded bg-ink-100 px-1.5 py-0.5">graph {chunk.graph_score.toFixed(2)}</span>
                  <span className="rounded bg-ink-100 px-1.5 py-0.5">{chunk.source}</span>
                </div>
              </details>
            ))}
          </div>
        </Card>
      ) : null}

      {answer.warnings.length > 0 ? (
        <div className="space-y-1 rounded-lg bg-amber-50 px-3 py-2">
          {answer.warnings.map((warning) => (
            <p key={warning} className="text-[11px] text-amber-700">
              {warning}
            </p>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export default function DocumentsPage() {
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState<string | null>(null);

  const documents = useQuery({ queryKey: ["documents"], queryFn: () => listDocuments() });

  const answer = useQuery({
    queryKey: ["answer", submitted],
    queryFn: () => askDocuments(submitted as string, undefined, 6),
    enabled: Boolean(submitted),
  });

  const index = useMutation({
    mutationFn: indexDocuments,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents"] }),
  });

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Knowledge base"
        title="Answers with page-level citations"
        description="Hybrid retrieval over manuals, bulletins and spec sheets. The answer is extractive and refuses when evidence is missing."
        actions={
          <Button variant="outline" loading={index.isPending} onClick={() => index.mutate()}>
            <RefreshCw className="h-4 w-4" /> Rebuild index
          </Button>
        }
      />

      {index.isError ? <ErrorState message={(index.error as Error).message} /> : null}
      {index.data ? (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-xs text-emerald-700">
          <CheckCircle2 className="h-4 w-4" />
          Indexed {index.data.documents} documents into {index.data.chunks} chunks ·{" "}
          {index.data.vocab_size.toLocaleString()} terms · {Math.round(index.data.latency_ms)} ms
        </div>
      ) : null}

      <Card className="p-4">
        <form
          className="flex flex-col gap-2 sm:flex-row"
          onSubmit={(event) => {
            event.preventDefault();
            if (query.trim()) setSubmitted(query.trim());
          }}
        >
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="e.g. What is the correct installation torque for a ball bearing?"
              className="pl-9"
            />
          </div>
          <Button type="submit" variant="accent" loading={answer.isFetching && Boolean(submitted)}>
            <FileSearch className="h-4 w-4" /> Search knowledge
          </Button>
        </form>
      </Card>

      {answer.isError ? <ErrorState message={(answer.error as Error).message} /> : null}
      {submitted ? (
        answer.isLoading ? (
          <Skeleton className="h-40 rounded-xl" />
        ) : answer.data ? (
          <AnswerPanel answer={answer.data} />
        ) : null
      ) : null}

      <Card>
        <CardHeader
          icon={FileText}
          title="Document library"
          description={
            documents.data ? `${documents.data.length} documents in the corpus` : "Loading corpus…"
          }
        />
        {documents.isError ? (
          <div className="p-5">
            <ErrorState message={(documents.error as Error).message} />
          </div>
        ) : documents.isLoading ? (
          <div className="space-y-2 p-5">
            {Array.from({ length: 6 }).map((_, index) => (
              <Skeleton key={index} className="h-9" />
            ))}
          </div>
        ) : documents.data && documents.data.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="text-[10px] uppercase tracking-wider text-ink-400">
                  <th className="px-5 pb-2 font-medium">Title</th>
                  <th className="px-5 pb-2 font-medium">Type</th>
                  <th className="px-5 pb-2 font-medium">Category</th>
                  <th className="px-5 pb-2 font-medium">Source</th>
                  <th className="px-5 pb-2 text-right font-medium">Chunks</th>
                  <th className="px-5 pb-2 text-right font-medium">Status</th>
                  <th className="px-5 pb-2 text-right font-medium">Added</th>
                </tr>
              </thead>
              <tbody>
                {documents.data.map((document) => (
                  <tr key={document.id} className="border-t border-ink-100">
                    <td className="px-5 py-2.5 text-xs font-medium text-ink-800">{document.title}</td>
                    <td className="px-5 py-2.5 text-xs text-ink-500">{titleCase(document.doc_type)}</td>
                    <td className="px-5 py-2.5 text-xs text-ink-500">{document.category ?? "—"}</td>
                    <td className="px-5 py-2.5 text-xs text-ink-500">{titleCase(document.source)}</td>
                    <td className="px-5 py-2.5 text-right text-xs tabular-nums text-ink-700">{document.chunks}</td>
                    <td className="px-5 py-2.5 text-right">
                      <Badge tone={document.approved ? "success" : "warning"}>
                        {document.approved ? "approved" : "draft"}
                      </Badge>
                    </td>
                    <td className="px-5 py-2.5 text-right text-xs text-ink-400">{formatDate(document.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No documents indexed" description="Seed the demo dataset to populate the corpus." />
        )}
      </Card>
    </div>
  );
}
