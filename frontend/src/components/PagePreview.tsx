/**
 * PagePreview.tsx
 *
 * Responsibilities:
 *   - Display page thumbnails with selection checkboxes
 *   - Language selection
 *   - Start processing with selected pages
 */

import { useState, useMemo } from "react";
import {
    Check,
    X,
    Globe,
    FileText,
    Loader2,
    AlertTriangle,
    ChevronLeft,
    Play,
    Eye,
} from "lucide-react";
import { uploadPdf, type PageInfo } from "../api";

const LANGUAGES = [
    { value: "Spanish", label: "🇪🇸 Spanish" },
    { value: "French", label: "🇫🇷 French" },
    { value: "German", label: "🇩🇪 German" },
    { value: "Japanese", label: "🇯🇵 Japanese" },
    { value: "Chinese", label: "🇨🇳 Chinese" },
    { value: "Italian", label: "🇮🇹 Italian" },
    { value: "Portuguese", label: "🇵🇹 Portuguese" },
    { value: "Dutch", label: "🇳🇱 Dutch" },
];

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface Props {
    file: File;
    pages: PageInfo[];
    onProcessingStarted: (jobId: string) => void;
    onBack: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function PagePreview({
    file,
    pages,
    onProcessingStarted,
    onBack,
}: Props) {
    const [selectedPages, setSelectedPages] = useState<Set<number>>(
        () => new Set(pages.filter(p => p.has_text).map(p => p.page_num))
    );
    const [lang, setLang] = useState(LANGUAGES[0].value);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const allSelected = selectedPages.size === pages.length;
    const hasTextPages = pages.filter(p => p.has_text);
    const noTextPages = pages.filter(p => !p.has_text);

    const togglePage = (pageNum: number) => {
        setSelectedPages(prev => {
            const next = new Set(prev);
            if (next.has(pageNum)) {
                next.delete(pageNum);
            } else {
                next.add(pageNum);
            }
            return next;
        });
    };

    const toggleAll = () => {
        if (allSelected) {
            setSelectedPages(new Set());
        } else {
            setSelectedPages(new Set(pages.map(p => p.page_num)));
        }
    };

    const handleSubmit = async () => {
        if (selectedPages.size === 0) {
            setError("Please select at least one page to translate");
            return;
        }
        setLoading(true);
        setError(null);
        try {
            const selectedArray = Array.from(selectedPages).sort((a, b) => a - b);
            const jobId = await uploadPdf(file, lang, selectedArray);
            onProcessingStarted(jobId);
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : "Upload failed");
            setLoading(false);
        }
    };

    return (
        <div className="max-w-6xl mx-auto pt-6 space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
                        <Eye className="w-6 h-6 text-indigo-400" />
                        Preview & Select Pages
                    </h2>
                    <p className="text-slate-400 text-sm mt-1">
                        {pages.length} pages · {(file.size / 1024).toFixed(1)} KB
                    </p>
                </div>
                <button
                    onClick={onBack}
                    className="flex items-center gap-2 text-slate-400 hover:text-slate-200 transition-colors"
                >
                    <ChevronLeft className="w-4 h-4" />
                    Back
                </button>
            </div>

            {/* Info bar */}
            <div className="flex flex-wrap items-center gap-4 text-sm">
                <div className="flex items-center gap-2 text-slate-300">
                    <Check className="w-4 h-4 text-green-400" />
                    <span>{selectedPages.size} selected</span>
                </div>
                <div className="flex items-center gap-2 text-slate-300">
                    <FileText className="w-4 h-4 text-indigo-400" />
                    <span>{hasTextPages.length} with text</span>
                </div>
                {noTextPages.length > 0 && (
                    <div className="flex items-center gap-2 text-amber-400">
                        <AlertTriangle className="w-4 h-4" />
                        <span>{noTextPages.length} image-only pages</span>
                    </div>
                )}
            </div>

            {/* Language selector */}
            <div className="glass-card p-4">
                <label className="label-sm flex items-center gap-2 mb-3">
                    <Globe className="w-3.5 h-3.5" /> Target Language
                </label>
                <div className="flex flex-wrap gap-2">
                    {LANGUAGES.map(({ value, label }) => (
                        <button
                            key={value}
                            onClick={() => setLang(value)}
                            className={[
                                "py-2 px-4 rounded-xl text-sm font-medium border transition-all",
                                lang === value
                                    ? "bg-indigo-600 border-indigo-500 text-white"
                                    : "bg-slate-800 border-slate-700 text-slate-300 hover:border-slate-500",
                            ].join(" ")}
                        >
                            {label}
                        </button>
                    ))}
                </div>
            </div>

            {/* Page grid */}
            <div className="space-y-3">
                <div className="flex items-center justify-between">
                    <h3 className="text-lg font-semibold text-slate-200">
                        Select Pages to Translate
                    </h3>
                    <button
                        onClick={toggleAll}
                        className="text-sm text-indigo-400 hover:text-indigo-300 transition-colors"
                    >
                        {allSelected ? "Deselect All" : "Select All"}
                    </button>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
                    {pages.map((page) => {
                        const isSelected = selectedPages.has(page.page_num);
                        const hasText = page.has_text;

                        return (
                            <div
                                key={page.page_num}
                                onClick={() => togglePage(page.page_num)}
                                className={[
                                    "relative group cursor-pointer rounded-xl overflow-hidden",
                                    "border-2 transition-all duration-200",
                                    isSelected
                                        ? "border-indigo-500 ring-2 ring-indigo-500/20"
                                        : "border-slate-700 hover:border-slate-500",
                                ].join(" ")}
                            >
                                {/* Thumbnail */}
                                <div className="aspect-[3/4] bg-slate-800 relative">
                                    <img
                                        src={page.thumbnail}
                                        alt={`Page ${page.page_num + 1}`}
                                        className="w-full h-full object-contain"
                                    />
                                    
                                    {/* Overlay for non-selected */}
                                    {!isSelected && (
                                        <div className="absolute inset-0 bg-slate-900/40 transition-opacity" />
                                    )}

                                    {/* Selection indicator */}
                                    <div
                                        className={[
                                            "absolute top-2 right-2 w-6 h-6 rounded-full",
                                            "flex items-center justify-center transition-colors",
                                            isSelected
                                                ? "bg-indigo-500 text-white"
                                                : "bg-slate-700/80 text-slate-400",
                                        ].join(" ")}
                                    >
                                        {isSelected && <Check className="w-4 h-4" />}
                                    </div>

                                    {/* No text warning */}
                                    {!hasText && (
                                        <div className="absolute bottom-0 left-0 right-0 bg-amber-600/90 text-white text-xs py-1 px-2 text-center">
                                            No text detected
                                        </div>
                                    )}
                                </div>

                                {/* Page number */}
                                <div className="p-2 bg-slate-800/80 text-center">
                                    <span className="text-sm text-slate-300">
                                        Page {page.page_num + 1}
                                    </span>
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Error message */}
            {error && (
                <p className="text-red-400 text-sm text-center bg-red-950/30 border border-red-800/50 rounded-xl p-3">
                    {error}
                </p>
            )}

            {/* Action buttons */}
            <div className="flex items-center justify-end gap-4 pt-4 border-t border-slate-700/50">
                <button
                    onClick={onBack}
                    className="px-6 py-3 rounded-xl text-slate-300 hover:text-slate-100 transition-colors"
                >
                    Cancel
                </button>
                <button
                    onClick={handleSubmit}
                    disabled={selectedPages.size === 0 || loading}
                    className={[
                        "btn-primary flex items-center gap-2 px-8 py-3",
                        (selectedPages.size === 0 || loading) && "opacity-50 cursor-not-allowed",
                    ].join(" ")}
                >
                    {loading ? (
                        <>
                            <Loader2 className="w-5 h-5 animate-spin" />
                            Starting...
                        </>
                    ) : (
                        <>
                            <Play className="w-5 h-5" />
                            Translate {selectedPages.size} Page{selectedPages.size !== 1 ? "s" : ""}
                        </>
                    )}
                </button>
            </div>
        </div>
    );
}
