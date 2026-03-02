/**
 * WorkflowTracker.tsx
 *
 * Responsibilities:
 *   - Connect to WS /ws/{jobId}
 *   - Display sequential pipeline nodes with animated states
 *   - Show terminal-style log window
 */

import { useEffect, useRef, useState } from "react";
import {
    FileSearch2,
    Languages,
    ShieldCheck,
    FileOutput,
    CheckCircle2,
    Circle,
    Loader2,
} from "lucide-react";
import { WS_BASE } from "../api";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------


// Pipeline stages — order matters.
const STAGES = [
    { key: "extract", label: "Extract Layout", icon: FileSearch2 },
    { key: "translate", label: "Translate", icon: Languages },
    { key: "validate", label: "Validate", icon: ShieldCheck },
    { key: "reconstruct", label: "Reconstruct PDF", icon: FileOutput },
] as const;

type StageKey = (typeof STAGES)[number]["key"];

// Map log message fragments → active stage
const STAGE_TRIGGERS: { fragment: string; stage: StageKey }[] = [
    { fragment: "Extracting", stage: "extract" },
    { fragment: "Chunking", stage: "extract" },
    { fragment: "Translating", stage: "translate" },
    { fragment: "Judge", stage: "validate" },
    { fragment: "Reconstructing", stage: "reconstruct" },
];

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type StageStatus = "idle" | "active" | "done";

interface StageState {
    extract: StageStatus;
    translate: StageStatus;
    validate: StageStatus;
    reconstruct: StageStatus;
}

interface Props {
    jobId: string;
    onDone: () => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const INITIAL_STAGES: StageState = {
    extract: "idle", translate: "idle", validate: "idle", reconstruct: "idle",
};

function resolveActiveStage(msg: string): StageKey | null {
    for (const { fragment, stage } of STAGE_TRIGGERS) {
        if (msg.includes(fragment)) return stage;
    }
    return null;
}

function advanceStages(prev: StageState, active: StageKey): StageState {
    const order: StageKey[] = ["extract", "translate", "validate", "reconstruct"];
    const activeIdx = order.indexOf(active);
    const next = { ...prev };
    order.forEach((key, idx) => {
        if (idx < activeIdx) next[key] = "done";
        if (idx === activeIdx) next[key] = "active";
    });
    return next;
}

function completeAllStages(prev: StageState): StageState {
    return {
        extract: "done", translate: "done",
        validate: "done", reconstruct: "done",
    };
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function NodeIcon({ status, IconComp }: {
    status: StageStatus;
    IconComp: React.ElementType;
}) {
    if (status === "done") return <CheckCircle2 className="w-5 h-5 text-emerald-400" />;
    if (status === "active") return <Loader2 className="w-5 h-5 text-indigo-400 animate-spin" />;
    return <Circle className="w-5 h-5 text-slate-600" />;
}

function PipelineNode({
    label,
    status,
    IconComp,
}: {
    label: string;
    status: StageStatus;
    IconComp: React.ElementType;
}) {
    const nodeClass = {
        idle: "node-idle",
        active: "node-active",
        done: "node-done",
    }[status];

    return (
        <div
            className={[
                "flex flex-col items-center gap-2 p-4 rounded-2xl border",
                "transition-all duration-500 min-w-[110px]",
                nodeClass,
            ].join(" ")}
        >
            <IconComp className="w-6 h-6" />
            <span className="text-xs font-semibold text-center leading-tight">
                {label}
            </span>
            <NodeIcon status={status} IconComp={IconComp} />
        </div>
    );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function WorkflowTracker({ jobId, onDone }: Props) {
    const [stages, setStages] = useState<StageState>(INITIAL_STAGES);
    const [logs, setLogs] = useState<string[]>([]);
    const [wsError, setWsError] = useState<string | null>(null);
    const logRef = useRef<HTMLDivElement>(null);

    // Auto-scroll log window to bottom on new messages.
    useEffect(() => {
        if (logRef.current) {
            logRef.current.scrollTop = logRef.current.scrollHeight;
        }
    }, [logs]);

    // Connect to WebSocket.
    useEffect(() => {
        const ws = new WebSocket(`${WS_BASE}/ws/${jobId}`);

        ws.onmessage = ({ data }: MessageEvent<string>) => {
            const msg = data as string;
            setLogs((prev) => [...prev, msg]);

            if (msg === "Done") {
                setStages(completeAllStages);
                onDone();
                return;
            }

            if (msg.startsWith("ERROR:")) {
                setWsError(msg);
                return;
            }

            const active = resolveActiveStage(msg);
            if (active) {
                setStages((prev) => advanceStages(prev, active));
            }
        };

        ws.onerror = () => setWsError("WebSocket connection failed.");

        return () => ws.close();
    }, [jobId, onDone]);

    return (
        <div className="max-w-3xl mx-auto pt-10 space-y-8">
            {/* Heading */}
            <div className="text-center space-y-1">
                <h2 className="text-2xl font-bold">Processing Document</h2>
                <p className="text-sm text-slate-400">
                    AI pipeline is running · Job{" "}
                    <code className="font-mono text-indigo-400">{jobId.slice(0, 8)}…</code>
                </p>
            </div>

            {/* Pipeline nodes */}
            <div className="glass-card p-6">
                <div className="flex flex-wrap justify-center gap-3">
                    {STAGES.map(({ key, label, icon }, i) => (
                        <div key={key} className="flex items-center gap-3">
                            <PipelineNode
                                label={label}
                                status={stages[key]}
                                IconComp={icon}
                            />
                            {i < STAGES.length - 1 && (
                                <div className="w-6 h-px bg-slate-700" />
                            )}
                        </div>
                    ))}
                </div>
            </div>

            {/* Terminal log window */}
            <div className="glass-card overflow-hidden">
                <div className="px-4 py-2 border-b border-slate-700/50 flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-red-500/70" />
                    <span className="w-2.5 h-2.5 rounded-full bg-yellow-500/70" />
                    <span className="w-2.5 h-2.5 rounded-full bg-green-500/70" />
                    <span className="ml-2 label-sm">Pipeline Log</span>
                </div>
                <div
                    id="log-window"
                    ref={logRef}
                    className="h-56 overflow-y-auto p-4 font-mono text-xs space-y-1 text-slate-300"
                >
                    {logs.length === 0 && (
                        <span className="text-slate-600">Waiting for pipeline…</span>
                    )}
                    {logs.map((line, i) => (
                        <div
                            key={i}
                            className={
                                line.startsWith("[WARN]")
                                    ? "text-yellow-400"
                                    : line.startsWith("ERROR")
                                        ? "text-red-400"
                                        : line.startsWith("[INFO]")
                                            ? "text-slate-300"
                                            : "text-indigo-300"
                            }
                        >
                            {line}
                        </div>
                    ))}
                </div>
            </div>

            {/* Error state */}
            {wsError && (
                <p className="text-red-400 text-sm text-center bg-red-950/30 border border-red-800/50 rounded-xl p-3">
                    {wsError}
                </p>
            )}
        </div>
    );
}
