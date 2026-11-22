"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, PackageSearch, Search, SlidersHorizontal } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import {
  getCategories,
  getManufacturers,
  searchParts,
  type PartSummary,
} from "@/lib/api";
import { cn, formatCurrency, titleCase } from "@/lib/utils";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Input,
  PageHeader,
  Select,
  Skeleton,
} from "@/components/ui";

const PAGE_SIZE = 15;

function useDebounced<T>(value: T, delay = 300) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

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

function ResultRow({ part }: { part: PartSummary }) {
  return (
    <tr className="group border-t border-ink-100 transition-colors hover:bg-ink-50/70">
      <td className="px-5 py-3">
        <Link href={`/parts/${part.id}`} className="font-mono text-xs font-medium text-ink-900 group-hover:text-accent-600">
          {part.part_number}
        </Link>
      </td>
      <td className="px-5 py-3">
        <Link href={`/parts/${part.id}`} className="text-sm text-ink-800">
          {part.name}
        </Link>
        {part.description ? (
          <p className="mt-0.5 line-clamp-1 max-w-md text-xs text-ink-400">{part.description}</p>
        ) : null}
      </td>
      <td className="px-5 py-3 text-xs text-ink-500">{part.category?.name ?? "—"}</td>
      <td className="px-5 py-3 text-xs text-ink-500">{part.manufacturer?.name ?? "—"}</td>
      <td className="px-5 py-3">
        <Badge tone={criticalityTone(part.criticality)}>{part.criticality}</Badge>
      </td>
      <td className="px-5 py-3 text-right text-xs tabular-nums text-ink-700">
        {formatCurrency(part.price, part.currency)}
      </td>
      <td className="px-5 py-3 text-right">
        <Badge tone={part.status === "active" ? "success" : part.status === "superseded" ? "warning" : "neutral"}>
          {part.status}
        </Badge>
      </td>
      <td className="px-5 py-3 text-right">
        <Link href={`/parts/${part.id}`} className="inline-flex text-ink-300 transition-colors group-hover:text-accent-500">
          <ArrowRight className="h-4 w-4" />
        </Link>
      </td>
    </tr>
  );
}

export default function CatalogPage() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [manufacturer, setManufacturer] = useState("");
  const [criticality, setCriticality] = useState("");
  const [inStock, setInStock] = useState(false);
  const [page, setPage] = useState(0);

  const debouncedQuery = useDebounced(query);
  const offset = page * PAGE_SIZE;

  useEffect(() => {
    setPage(0);
  }, [debouncedQuery, category, manufacturer, criticality, inStock]);

  const filters = useMemo(
    () => ({
      query: debouncedQuery || undefined,
      category: category || undefined,
      manufacturer: manufacturer || undefined,
      criticality: criticality || undefined,
      in_stock_only: inStock || undefined,
      limit: PAGE_SIZE,
      offset,
    }),
    [debouncedQuery, category, manufacturer, criticality, inStock, offset],
  );

  const parts = useQuery({
    queryKey: ["parts", filters],
    queryFn: () => searchParts(filters),
    placeholderData: (previous) => previous,
  });
  const categories = useQuery({ queryKey: ["categories"], queryFn: getCategories });
  const manufacturers = useQuery({ queryKey: ["manufacturers"], queryFn: getManufacturers });

  const total = parts.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Catalog"
        title="Find the right part, fast"
        description="Fuzzy search across part numbers, names, descriptions and specifications, with filters for stock and criticality."
      />

      <Card className="p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search part number, name or spec — e.g. bearing 6205, V-belt, torque"
              className="pl-9"
            />
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:w-auto lg:grid-cols-3">
            <Select value={category} onChange={(event) => setCategory(event.target.value)} className="min-w-[150px]">
              <option value="">All categories</option>
              {categories.data?.map((item) => (
                <option key={item.id} value={item.slug}>
                  {item.name}
                </option>
              ))}
            </Select>
            <Select
              value={manufacturer}
              onChange={(event) => setManufacturer(event.target.value)}
              className="min-w-[150px]"
            >
              <option value="">All manufacturers</option>
              {manufacturers.data?.map((item) => (
                <option key={item.id} value={item.name}>
                  {item.name}
                </option>
              ))}
            </Select>
            <Select
              value={criticality}
              onChange={(event) => setCriticality(event.target.value)}
              className="min-w-[130px]"
            >
              <option value="">Any criticality</option>
              {["low", "medium", "high", "critical"].map((level) => (
                <option key={level} value={level}>
                  {titleCase(level)}
                </option>
              ))}
            </Select>
          </div>
          <label className="flex shrink-0 cursor-pointer items-center gap-2 rounded-lg border border-ink-200 px-3 py-2 text-xs text-ink-600">
            <input
              type="checkbox"
              checked={inStock}
              onChange={(event) => setInStock(event.target.checked)}
              className="h-3.5 w-3.5 rounded border-ink-300 text-accent-500 focus:ring-accent-300"
            />
            In stock only
          </label>
        </div>
      </Card>

      {parts.isError ? <ErrorState message={(parts.error as Error).message} /> : null}

      <Card>
        <div className="flex items-center justify-between px-5 py-3">
          <p className="text-xs text-ink-500">
            {parts.isLoading ? "Searching…" : `${total.toLocaleString()} parts`}
            {debouncedQuery ? (
              <>
                {" "}
                for <span className="font-medium text-ink-700">“{debouncedQuery}”</span>
              </>
            ) : null}
          </p>
          <span className="flex items-center gap-1.5 text-[11px] text-ink-400">
            <SlidersHorizontal className="h-3 w-3" /> fuzzy + spec matching
          </span>
        </div>

        {parts.isLoading ? (
          <div className="space-y-2 border-t border-ink-100 p-5">
            {Array.from({ length: 8 }).map((_, index) => (
              <Skeleton key={index} className="h-10" />
            ))}
          </div>
        ) : parts.data && parts.data.items.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="text-[10px] uppercase tracking-wider text-ink-400">
                  <th className="px-5 pb-2 font-medium">Part no.</th>
                  <th className="px-5 pb-2 font-medium">Name</th>
                  <th className="px-5 pb-2 font-medium">Category</th>
                  <th className="px-5 pb-2 font-medium">Manufacturer</th>
                  <th className="px-5 pb-2 font-medium">Criticality</th>
                  <th className="px-5 pb-2 text-right font-medium">Price</th>
                  <th className="px-5 pb-2 text-right font-medium">Status</th>
                  <th className="px-5 pb-2" />
                </tr>
              </thead>
              <tbody>
                {parts.data.items.map((part) => (
                  <ResultRow key={part.id} part={part} />
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            icon={PackageSearch}
            title="No parts match these filters"
            description="Try a broader query or clear the category and stock filters."
            action={
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setQuery("");
                  setCategory("");
                  setManufacturer("");
                  setCriticality("");
                  setInStock(false);
                }}
              >
                Reset filters
              </Button>
            }
          />
        )}

        <div className="flex items-center justify-between border-t border-ink-100 px-5 py-3">
          <p className="text-[11px] text-ink-400">
            Page {page + 1} of {pageCount}
          </p>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage((value) => value - 1)}>
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page + 1 >= pageCount}
              onClick={() => setPage((value) => value + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      </Card>

      {parts.data?.synthetic_data ? (
        <p className="text-[11px] text-ink-400">
          Showing the bundled synthetic demo catalog. Swap DATABASE_URL to point PartScope at a real
          catalog.
        </p>
      ) : null}
    </div>
  );
}
