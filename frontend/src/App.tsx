/**
 * App.tsx — Root application with a simple view-state machine:
 *   "upload"     → UploadDashboard (file selection)
 *   "preview"    → PagePreview (page selection)
 *   "processing" → WorkflowTracker
 *   "done"       → OutputViewer
 */

import { useState } from "react";
import UploadDashboard from "./components/UploadDashboard";
import PagePreview from "./components/PagePreview";
import WorkflowTracker from "./components/WorkflowTracker";
import OutputViewer from "./components/OutputViewer";
import type { PageInfo } from "./api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type View = "upload" | "preview" | "processing" | "done";

interface JobInfo {
    jobId: string;
    originalFile: File;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function App() {
    const [view, setView] = useState<View>("upload");
    const [job, setJob] = useState<JobInfo | null>(null);
    const [file, setFile] = useState<File | null>(null);
    const [pages, setPages] = useState<PageInfo[]>([]);

    const handleFileSelected = (selectedFile: File, pageInfo: PageInfo[]) => {
        setFile(selectedFile);
        setPages(pageInfo);
        setView("preview");
    };

    const handleProcessingStarted = (jobId: string) => {
        if (file) {
            setJob({ jobId, originalFile: file });
            setView("processing");
        }
    };

    const handleProcessingDone = () => {
        setView("done");
    };

    const handleReset = () => {
        setJob(null);
        setFile(null);
        setPages([]);
        setView("upload");
    };

    const handleBackToUpload = () => {
        setView("upload");
        setFile(null);
        setPages([]);
    };

    return (
        <div className="min-h-screen flex flex-col">
            {/* Top bar */}
            <header className="border-b border-slate-700/50 px-6 py-4 flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center">
                    <span className="text-white text-sm font-bold">D</span>
                </div>
                <h1 className="text-lg font-semibold text-slate-100 tracking-tight">
                    DocuPreserve <span className="text-indigo-400">AI</span>
                </h1>
                {view !== "upload" && (
                    <button
                        onClick={handleReset}
                        className="ml-auto text-sm text-slate-400 hover:text-slate-200 transition-colors"
                    >
                        ← New Document
                    </button>
                )}
            </header>

            {/* Main content */}
            <main className="flex-1 p-6">
                {view === "upload" && (
                    <UploadDashboard onFileSelected={handleFileSelected} />
                )}
                {view === "preview" && file && (
                    <PagePreview
                        file={file}
                        pages={pages}
                        onProcessingStarted={handleProcessingStarted}
                        onBack={handleBackToUpload}
                    />
                )}
                {view === "processing" && job && (
                    <WorkflowTracker
                        jobId={job.jobId}
                        onDone={handleProcessingDone}
                    />
                )}
                {view === "done" && job && (
                    <OutputViewer
                        jobId={job.jobId}
                        originalFile={job.originalFile}
                    />
                )}
            </main>
        </div>
    );
}
