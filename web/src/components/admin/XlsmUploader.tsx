"use client";

import { useRef, useState, type DragEvent, type ChangeEvent } from "react";

import { messages } from "@/lib/i18n";
import { useUploadImports } from "@/lib/query/hooks";

/**
 * Drag-drop xlsm uploader.
 *
 * Accepts one or more .xlsm files; each is sent as a multipart part to
 * POST /api/imports.  The server returns 202 with the Import rows
 * (status=pending) and a background task does the actual parse/write.
 * The on-success callback gets the list of new Import ids so the parent
 * can navigate or render polling state.
 */
export function XlsmUploader({ onComplete }: { onComplete?: (importIds: number[]) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const mutation = useUploadImports();

  const submit = async (files: FileList | File[] | null) => {
    if (!files || (files instanceof FileList ? files.length === 0 : files.length === 0)) {
      return;
    }
    const list = Array.from(files as ArrayLike<File>);
    const accepted = list.filter((f) => f.name.toLowerCase().endsWith(".xlsm"));
    if (accepted.length === 0) return;
    const rows = await mutation.mutateAsync(accepted);
    onComplete?.(rows.map((r) => r.id));
  };

  return (
    <div className="space-y-2">
      <label
        htmlFor="xlsm-upload"
        className={[
          "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed bg-white px-4 py-10 text-center transition-colors",
          dragOver
            ? "border-slate-900 bg-slate-50"
            : "border-slate-300 text-slate-600 hover:border-slate-500",
        ].join(" ")}
        onDragOver={(e: DragEvent<HTMLLabelElement>) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e: DragEvent<HTMLLabelElement>) => {
          e.preventDefault();
          setDragOver(false);
          void submit(e.dataTransfer.files);
        }}
      >
        <svg
          className="h-10 w-10 text-slate-400"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.5}
          aria-hidden
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 16V4m0 0l-4 4m4-4l4 4M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2"
          />
        </svg>
        <span className="text-sm font-medium text-slate-800">{messages.uploadDropHere}</span>
        <span className="text-xs text-slate-500">{messages.uploadHint}</span>
        <input
          ref={inputRef}
          id="xlsm-upload"
          type="file"
          accept=".xlsm,application/vnd.ms-excel.sheet.macroEnabled.12"
          multiple
          className="sr-only"
          onChange={(e: ChangeEvent<HTMLInputElement>) => {
            void submit(e.target.files);
            // clear so the same file can be re-selected after a failure
            if (inputRef.current) inputRef.current.value = "";
          }}
        />
      </label>
      {mutation.isPending && (
        <p className="text-sm text-slate-600" role="status">
          {messages.uploadInProgress}
        </p>
      )}
      {mutation.isError && (
        <p className="text-sm text-overdue" role="alert">
          {messages.uploadFailed}
          {mutation.error instanceof Error ? ` — ${mutation.error.message}` : ""}
        </p>
      )}
    </div>
  );
}
