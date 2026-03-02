/**
 * api.ts — Centralised API/WebSocket base URLs.
 *
 * Vite replaces import.meta.env.VITE_API_URL at build time.
 * Locally (npm run dev):   falls back to http://localhost:8000
 * Docker / production:     uses the VITE_API_URL build arg
 */

export const API_BASE: string =
    import.meta.env.VITE_API_URL ?? "http://localhost:8000";

/** Convert http(s) → ws(s) for WebSocket connections. */
export const WS_BASE: string = API_BASE.replace(/^http/, "ws");

/** Page info from preview endpoint */
export interface PageInfo {
    page_num: number;
    thumbnail: string;
    has_text: boolean;
    width: number;
    height: number;
}

/** Preview response from backend */
export interface PreviewResponse {
    pages: PageInfo[];
}

/**
 * Fetch page previews for a PDF file.
 */
export async function fetchPreview(file: File): Promise<PreviewResponse> {
    const form = new FormData();
    form.append("file", file);

    const res = await fetch(`${API_BASE}/preview`, {
        method: "POST",
        body: form,
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Preview failed" }));
        throw new Error(err.detail ?? "Preview failed");
    }

    return res.json();
}

/**
 * Upload PDF with optional page selection for translation.
 */
export async function uploadPdf(
    file: File,
    lang: string,
    selectedPages?: number[]
): Promise<string> {
    const form = new FormData();
    form.append("file", file);
    form.append("target_lang", lang);
    if (selectedPages && selectedPages.length > 0) {
        form.append("selected_pages", JSON.stringify(selectedPages));
    }

    const res = await fetch(`${API_BASE}/upload`, {
        method: "POST",
        body: form,
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Upload failed" }));
        throw new Error(err.detail ?? "Upload failed");
    }

    const data = await res.json();
    return data.job_id as string;
}
