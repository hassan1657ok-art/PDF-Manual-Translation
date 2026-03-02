/**
 * UploadDashboard.tsx
 *
 * Responsibilities:
 *   - Drag-and-drop PDF upload zone
 *   - Fetch page previews from backend
 *   - Pass file and preview data to parent
 */

import { useState, useCallback, DragEvent, ChangeEvent } from "react";
import { UploadCloud, FileText, Loader2, AlertCircle } from "lucide-react";
import { fetchPreview, type PageInfo } from "../api";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface Props {
    onFileSelected: (file: File, pages: PageInfo[]) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function UploadDashboard({ onFileSelected }: Props) {
    const [file, setFile] = useState<File | null>(null);
    const [dragging, setDragging] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // ── Drop zone handlers ──────────────────────────────────────────────────

    const acceptFile = useCallback(async (f: File) => {
        if (!f.name.toLowerCase().endsWith(".pdf")) {
            setError("Please upload a PDF file.");
            return;
        }
        setError(null);
        setFile(f);
        setLoading(true);
        
        try {
            const preview = await fetchPreview(f);
            onFileSelected(f, preview.pages);
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : "Failed to preview PDF");
            setFile(null);
        } finally {
            setLoading(false);
        }
    }, [onFileSelected]);

    const onDrop = useCallback(
        (e: DragEvent<HTMLDivElement>) => {
            e.preventDefault();
            setDragging(false);
            const dropped = e.dataTransfer.files[0];
            if (dropped) acceptFile(dropped);
        },
        [acceptFile]
    );

    const onFileChange = useCallback(
        (e: ChangeEvent<HTMLInputElement>) => {
            const picked = e.target.files?.[0];
            if (picked) acceptFile(picked);
        },
        [acceptFile]
    );

    // ── Render ──────────────────────────────────────────────────────────────

    return (
        <div className="max-w-2xl mx-auto pt-12 space-y-8">
            {/* Heading */}
            <div className="text-center space-y-2">
                <h2 className="text-3xl font-bold text-slate-100">
                    Upload Your Document
                </h2>
                <p className="text-slate-400 text-sm">
                    Supports text-based PDFs. Layout is preserved at pixel accuracy.
                </p>
            </div>

            {/* Drop zone */}
            <div
                id="drop-zone"
                onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={onDrop}
                className={[
                    "glass-card p-10 flex flex-col items-center justify-center gap-4",
                    "border-2 border-dashed cursor-pointer transition-all duration-200",
                    dragging
                        ? "border-indigo-500 bg-indigo-950/30"
                        : "border-slate-600 hover:border-slate-500",
                    loading && "opacity-60 pointer-events-none",
                ].join(" ")}
                onClick={() => !loading && document.getElementById("file-input")?.click()}
            >
                <input
                    id="file-input"
                    type="file"
                    accept=".pdf"
                    title="Select a PDF file"
                    className="hidden"
                    onChange={onFileChange}
                    disabled={loading}
                />

                {loading ? (
                    <>
                        <Loader2 className="w-12 h-12 text-indigo-400 animate-spin" />
                        <div className="text-center">
                            <p className="font-medium text-slate-300">
                                Analyzing document...
                            </p>
                            <p className="text-sm text-slate-500">Extracting page previews</p>
                        </div>
                    </>
                ) : file ? (
                    <>
                        <FileText className="w-12 h-12 text-indigo-400" />
                        <div className="text-center">
                            <p className="font-semibold text-slate-200">{file.name}</p>
                            <p className="text-sm text-slate-400">
                                {(file.size / 1024).toFixed(1)} KB · Click to change
                            </p>
                        </div>
                    </>
                ) : (
                    <>
                        <UploadCloud className="w-12 h-12 text-slate-500" />
                        <div className="text-center">
                            <p className="font-medium text-slate-300">
                                Drag & drop a PDF here
                            </p>
                            <p className="text-sm text-slate-500">or click to browse</p>
                        </div>
                    </>
                )}
            </div>

            {/* Info card */}
            <div className="glass-card p-5 space-y-3">
                <div className="flex items-start gap-3 text-slate-400 text-sm">
                    <AlertCircle className="w-5 h-5 text-indigo-400 flex-shrink-0 mt-0.5" />
                    <div>
                        <p className="font-medium text-slate-300 mb-1">What happens next?</p>
                        <p>After uploading, you'll be able to preview each page and select which ones to translate. This helps you save time and API costs by only processing the pages you need.</p>
                    </div>
                </div>
            </div>

            {/* Error message */}
            {error && (
                <p className="text-red-400 text-sm text-center bg-red-950/30 border border-red-800/50 rounded-xl p-3">
                    {error}
                </p>
            )}
        </div>
    );
}
