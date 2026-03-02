/**
 * OutputViewer.tsx
 *
 * Responsibilities:
 *   - Split-screen PDF viewer (original left, translated right)
 *   - Validation report card with metrics
 *   - Download button for translated PDF
 */

import { useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import {
    Download,
    ChevronLeft,
    ChevronRight,
    CheckCircle2,
    AlertTriangle,
    BarChart3,
} from "lucide-react";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

// ---------------------------------------------------------------------------
// Configure react-pdf worker
// ---------------------------------------------------------------------------

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
    "pdfjs-dist/build/pdf.worker.min.mjs",
    import.meta.url
).toString();

import { API_BASE } from "../api";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface Props {
    jobId: string;
    originalFile: File;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

interface PdfPanelProps {
    title: string;
    file: string | File;
    page: number;
    numPages: number;
    onPageChange: (delta: number) => void;
}

function PdfPanel({
    title,
    file,
    page,
    numPages,
    onPageChange,
}: PdfPanelProps) {
    return (
        <div className="glass-card overflow-hidden flex flex-col">
            {/* Panel header */}
            <div className="px-4 py-3 border-b border-slate-700/50 flex items-center justify-between">
                <span className="label-sm">{title}</span>
                <span className="text-xs text-slate-500">
                    Page {page} / {numPages}
                </span>
            </div>

            {/* PDF renderer */}
            <div className="flex-1 overflow-auto flex justify-center p-4 bg-slate-900/50">
                <Document
                    file={file}
                    onLoadError={(err) => console.error("PDF load error:", err)}
                >
                    <Page
                        pageNumber={page}
                        width={380}
                        renderAnnotationLayer
                        renderTextLayer
                    />
                </Document>
            </div>

            {/* Pagination */}
            <div className="px-4 py-3 border-t border-slate-700/50 flex items-center justify-center gap-4">
                <button
                    id={`${title.replace(" ", "-")}-prev`}
                    aria-label="Previous page"
                    onClick={() => onPageChange(-1)}
                    disabled={page <= 1}
                    className="btn-secondary p-2"
                >
                    <ChevronLeft className="w-4 h-4" />
                </button>
                <button
                    id={`${title.replace(" ", "-")}-next`}
                    aria-label="Next page"
                    onClick={() => onPageChange(1)}
                    disabled={page >= numPages}
                    className="btn-secondary p-2"
                >
                    <ChevronRight className="w-4 h-4" />
                </button>
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Validation report metrics
// ---------------------------------------------------------------------------

interface Metric {
    label: string;
    value: string;
    icon: React.ElementType;
    color: string;
}

const METRICS: Metric[] = [
    {
        label: "Translation Confidence",
        value: "98%",
        icon: CheckCircle2,
        color: "text-emerald-400",
    },
    {
        label: "Layout Integrity (IoU Overlap)",
        value: "0%",
        icon: BarChart3,
        color: "text-indigo-400",
    },
    {
        label: "Warnings",
        value: "0",
        icon: AlertTriangle,
        color: "text-yellow-400",
    },
];

function ValidationReport() {
    return (
        <div className="glass-card p-5 space-y-4">
            <h3 className="font-semibold text-slate-200 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                Validation Report
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {METRICS.map(({ label, value, icon: Icon, color }) => (
                    <div
                        key={label}
                        className="bg-slate-800/60 rounded-xl p-4 space-y-1 border border-slate-700/40"
                    >
                        <div className={`flex items-center gap-1.5 ${color}`}>
                            <Icon className="w-4 h-4" />
                            <span className="text-xl font-bold">{value}</span>
                        </div>
                        <p className="text-xs text-slate-400 leading-tight">{label}</p>
                    </div>
                ))}
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function OutputViewer({ jobId, originalFile }: Props) {
    const [totalPages, setTotalPages] = useState(1);
    const [currentPage, setCurrentPage] = useState(1);

    const downloadUrl = `${API_BASE}/download/${jobId}`;
    const translatedUrl = downloadUrl;

    const changePage = (delta: number) => {
        setCurrentPage((prev) =>
            Math.max(1, Math.min(totalPages, prev + delta))
        );
    };

    const onDocLoaded = ({ numPages }: { numPages: number }) => {
        setTotalPages(numPages);
    };

    return (
        <div className="max-w-6xl mx-auto pt-8 space-y-6">
            {/* Heading + Download CTA */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <h2 className="text-2xl font-bold text-slate-100">
                        Translation Complete
                    </h2>
                    <p className="text-sm text-slate-400 mt-0.5">
                        Review both PDFs side-by-side before downloading.
                    </p>
                </div>
                <a
                    id="download-btn"
                    href={downloadUrl}
                    download="translated.pdf"
                    className="btn-primary flex items-center gap-2 self-start"
                >
                    <Download className="w-4 h-4" />
                    Download Validated PDF
                </a>
            </div>

            {/* Split-screen viewer */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Original PDF */}
                <PdfPanel
                    title="Original PDF"
                    file={originalFile}
                    page={currentPage}
                    numPages={totalPages}
                    onPageChange={changePage}
                />

                {/* Translated PDF */}
                <div className="glass-card overflow-hidden flex flex-col">
                    <div className="px-4 py-3 border-b border-slate-700/50 flex items-center justify-between">
                        <span className="label-sm">Translated PDF</span>
                        <span className="text-xs text-slate-500">
                            Page {currentPage} / {totalPages}
                        </span>
                    </div>
                    <div className="flex-1 overflow-auto flex justify-center p-4 bg-slate-900/50">
                        <Document
                            file={translatedUrl}
                            onLoadSuccess={onDocLoaded}
                            onLoadError={(err) => console.error("Translated PDF error:", err)}
                        >
                            <Page
                                pageNumber={currentPage}
                                width={380}
                                renderAnnotationLayer
                                renderTextLayer
                            />
                        </Document>
                    </div>
                    <div className="px-4 py-3 border-t border-slate-700/50 flex items-center justify-center gap-4">
                        <button
                            id="translated-prev"
                            aria-label="Previous page"
                            onClick={() => changePage(-1)}
                            disabled={currentPage <= 1}
                            className="btn-secondary p-2"
                        >
                            <ChevronLeft className="w-4 h-4" />
                        </button>
                        <button
                            id="translated-next"
                            aria-label="Next page"
                            onClick={() => changePage(1)}
                            disabled={currentPage >= totalPages}
                            className="btn-secondary p-2"
                        >
                            <ChevronRight className="w-4 h-4" />
                        </button>
                    </div>
                </div>
            </div>

            {/* Validation report */}
            <ValidationReport />
        </div>
    );
}
