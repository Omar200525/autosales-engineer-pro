import type { CatalogStats, PipelineRunCreated, PipelineRunSnapshot, Product, SolutionReport } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

type PipelineRunPayload = {
  raw_brief: string;
  image_base64?: string;
  image_media_type?: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getCatalogStats(): Promise<CatalogStats> {
  return request<CatalogStats>("/api/catalog/stats");
}

export function getCatalogProducts(category?: string, query?: string): Promise<{ products: Product[]; count: number }> {
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  if (query) params.set("q", query);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return request<{ products: Product[]; count: number }>(`/api/catalog/products${suffix}`);
}

export function createPipelineRun(payload: PipelineRunPayload): Promise<PipelineRunCreated> {
  return request<PipelineRunCreated>("/api/pipeline/runs", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getPipelineRun(runId: string): Promise<PipelineRunSnapshot> {
  return request<PipelineRunSnapshot>(`/api/pipeline/runs/${runId}`);
}

export function streamPipelineRun(
  runId: string,
  handlers: {
    onStep: (event: MessageEvent) => void;
    onCompleted: (event: MessageEvent) => void;
    onFailed: (event: MessageEvent) => void;
    onError: () => void;
  }
): EventSource {
  const source = new EventSource(`${API_BASE}/api/pipeline/runs/${runId}/events`);
  source.addEventListener("step", handlers.onStep);
  source.addEventListener("completed", handlers.onCompleted);
  source.addEventListener("failed", handlers.onFailed);
  source.onerror = handlers.onError;
  return source;
}

export function downloadPdf(report: SolutionReport): void {
  fetch(`${API_BASE}/api/quotes/pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(report)
  })
    .then((response) => {
      if (!response.ok) throw new Error("PDF export failed");
      return response.blob();
    })
    .then((blob) => {
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `quote_${report.client_name.replace(/\s+/g, "_")}.pdf`;
      link.click();
      URL.revokeObjectURL(url);
    });
}
