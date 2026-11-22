"use client";

import { useMutation } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  Bot,
  CheckCircle2,
  ImageUp,
  ScanEye,
  ShieldAlert,
  Timer,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { identifyImage, uploadImage, type VisionIdentify } from "@/lib/api";
import { formatPercent } from "@/lib/utils";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorState,
  PageHeader,
  ProgressBar,
} from "@/components/ui";

export default function IdentifyPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  const identify = useMutation({ mutationFn: identifyImage });
  const upload = useMutation({ mutationFn: uploadImage });

  useEffect(() => {
    if (!file) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  function handleFile(next: File | null) {
    if (!next) return;
    setFile(next);
    identify.mutate(next);
    upload.mutate(next);
  }

  const result: VisionIdentify | undefined = identify.data;

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Vision identification"
        title="Point at a part, get ranked candidates"
        description="Image embeddings are matched against the catalog index. Low-confidence results are routed to human review instead of guessed."
        actions={
          <Badge tone="info">
            <ScanEye className="h-3 w-3" /> k-NN baseline · CPU
          </Badge>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[1fr_1.15fr]">
        <Card className="overflow-hidden">
          <CardHeader
            icon={ImageUp}
            title="Upload an image"
            description="JPG, PNG or WebP · max 8 MB · one part per frame"
          />
          <div className="p-5">
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              onDragOver={(event) => {
                event.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(event) => {
                event.preventDefault();
                setDragging(false);
                const dropped = event.dataTransfer.files?.[0];
                if (dropped) handleFile(dropped);
              }}
              className={`relative flex min-h-[280px] w-full flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-6 transition-colors ${
                dragging ? "border-accent-400 bg-accent-50" : "border-ink-200 bg-ink-50/60 hover:border-accent-300"
              }`}
            >
              {preview ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={preview} alt="Selected part" className="max-h-[300px] w-auto rounded-lg object-contain" />
              ) : (
                <>
                  <span className="flex h-12 w-12 items-center justify-center rounded-full bg-white text-ink-500 shadow-card">
                    <ImageUp className="h-5 w-5" />
                  </span>
                  <span className="text-sm font-medium text-ink-800">Drop a photo or click to browse</span>
                  <span className="text-xs text-ink-400">Renders, catalog shots or line photos</span>
                </>
              )}
            </button>
            <input
              ref={inputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="hidden"
              onChange={(event) => handleFile(event.target.files?.[0] ?? null)}
            />
            {file ? (
              <div className="mt-3 flex items-center justify-between gap-3 text-xs text-ink-500">
                <span className="truncate">{file.name}</span>
                <span className="shrink-0 tabular-nums">{(file.size / 1024).toFixed(0)} KB</span>
              </div>
            ) : null}
          </div>
        </Card>

        <Card>
          <CardHeader
            icon={ScanEye}
            title="Candidates"
            description={
              result
                ? `${result.model_name} ${result.model_version} · ${result.latency_ms.toFixed(1)} ms`
                : "Ranked matches with calibrated confidence"
            }
            action={
              result ? (
                <Badge tone={result.review_required ? "warning" : "success"}>
                  {result.review_required ? "review required" : "confident"}
                </Badge>
              ) : null
            }
          />

          {identify.isPending ? (
            <div className="flex flex-col items-center gap-3 px-5 py-16">
              <span className="h-8 w-8 animate-spin rounded-full border-2 border-ink-200 border-t-accent-500" />
              <p className="text-xs text-ink-500">Embedding and matching…</p>
            </div>
          ) : identify.isError ? (
            <div className="p-5">
              <ErrorState message={(identify.error as Error).message} />
            </div>
          ) : result ? (
            <div className="divide-y divide-ink-100">
              <div className="grid grid-cols-3 gap-3 px-5 py-4">
                <div>
                  <p className="text-[10px] uppercase tracking-wide text-ink-400">Confidence</p>
                  <p className="mt-1 text-lg font-semibold tabular-nums text-ink-900">
                    {formatPercent(result.confidence, 1)}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wide text-ink-400">Latency</p>
                  <p className="mt-1 flex items-center gap-1 text-lg font-semibold tabular-nums text-ink-900">
                    <Timer className="h-3.5 w-3.5 text-ink-400" />
                    {result.latency_ms.toFixed(1)}ms
                  </p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wide text-ink-400">Runtime</p>
                  <p className="mt-1 text-xs font-medium text-ink-700">
                    {result.runtime} · {result.precision}
                  </p>
                </div>
              </div>

              {result.top_candidates.map((candidate) => (
                <div key={`${candidate.rank}-${candidate.label}`} className="px-5 py-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="flex h-5 w-5 items-center justify-center rounded bg-ink-100 text-[10px] font-semibold text-ink-500">
                          {candidate.rank}
                        </span>
                        {candidate.part_id ? (
                          <Link
                            href={`/parts/${candidate.part_id}`}
                            className="text-sm font-medium text-ink-900 hover:text-accent-600"
                          >
                            {candidate.label}
                          </Link>
                        ) : (
                          <span className="text-sm font-medium text-ink-900">{candidate.label}</span>
                        )}
                      </div>
                      <p className="mt-0.5 pl-7 text-[11px] text-ink-400">
                        {candidate.part_number ?? "no catalog link"} · {candidate.category ?? "uncategorised"}
                      </p>
                    </div>
                    <span className="text-xs font-semibold tabular-nums text-ink-800">
                      {formatPercent(candidate.score, 1)}
                    </span>
                  </div>
                  <div className="mt-2 pl-7">
                    <ProgressBar value={candidate.score} tone={candidate.rank === 1 ? "accent" : "success"} />
                  </div>
                </div>
              ))}

              {result.review_required ? (
                <div className="flex items-start gap-2 bg-amber-50/60 px-5 py-3 text-xs text-amber-700">
                  <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
                  Confidence is below the review threshold. Confirm against the part number before
                  acting.
                </div>
              ) : (
                <div className="flex items-start gap-2 bg-emerald-50/60 px-5 py-3 text-xs text-emerald-700">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
                  Top match clears the confidence threshold.
                </div>
              )}

              {result.warnings.length > 0 ? (
                <div className="space-y-1 px-5 py-3">
                  {result.warnings.map((warning) => (
                    <p key={warning} className="flex items-start gap-2 text-[11px] text-ink-500">
                      <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0 text-amber-500" />
                      {warning}
                    </p>
                  ))}
                </div>
              ) : null}

              {upload.data ? (
                <div className="px-5 py-3 font-mono text-[10px] text-ink-400">
                  {upload.data.width}×{upload.data.height} · {upload.data.content_type} · sha256{" "}
                  {upload.data.sha256.slice(0, 16)}…
                </div>
              ) : null}

              {result.top_candidates[0]?.part_id ? (
                <div className="px-5 py-4">
                  <Link
                    href={`/chat?part_id=${result.top_candidates[0].part_id}&q=${encodeURIComponent(
                      "Confirm this identification and find compatible replacements",
                    )}`}
                  >
                    <Button variant="accent" className="w-full">
                      <Bot className="h-4 w-4" /> Continue in assistant <ArrowRight className="h-4 w-4" />
                    </Button>
                  </Link>
                </div>
              ) : null}
            </div>
          ) : (
            <EmptyState
              icon={ScanEye}
              title="No image yet"
              description="Upload a part photo to see the ranked candidate list."
            />
          )}
        </Card>
      </div>
    </div>
  );
}
