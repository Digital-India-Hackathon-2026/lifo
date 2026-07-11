import { useId, useRef, useState, type DragEvent, type KeyboardEvent } from "react";
import { UploadCloud, FileCheck2, X } from "lucide-react";
import clsx from "clsx";

interface FileDropzoneProps {
  accept: string;
  hint: string;
  prompt: string;
  file: File | null;
  onFileSelected: (file: File | null) => void;
  disabled?: boolean;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i++;
  }
  return `${value.toFixed(1)} ${units[i]}`;
}

export default function FileDropzone({
  accept,
  hint,
  prompt,
  file,
  onFileSelected,
  disabled = false,
}: FileDropzoneProps) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);

  const openPicker = () => {
    if (!disabled) inputRef.current?.click();
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      openPicker();
    }
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragActive(false);
    if (disabled) return;
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) onFileSelected(dropped);
  };

  if (file) {
    return (
      <div className="glass-card flex items-center justify-between gap-3 rounded-xl p-4">
        <div className="flex min-w-0 items-center gap-3">
          <FileCheck2 className="h-5 w-5 shrink-0 text-brand" aria-hidden="true" />
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-ink">{file.name}</p>
            <p className="text-xs text-ink-dim">{formatBytes(file.size)}</p>
          </div>
        </div>
        {!disabled && (
          <button
            type="button"
            onClick={() => onFileSelected(null)}
            aria-label="Remove selected file"
            className="cursor-pointer rounded-md p-1.5 text-ink-dim transition-colors hover:bg-ink/5 hover:text-ink"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
    );
  }

  return (
    <div
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled}
      onClick={openPicker}
      onKeyDown={handleKeyDown}
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setDragActive(true);
      }}
      onDragLeave={() => setDragActive(false)}
      onDrop={handleDrop}
      className={clsx(
        "glass-card flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed p-8 text-center outline-none transition-colors",
        dragActive ? "border-brand bg-brand-dim/40" : "border-border",
        disabled && "cursor-not-allowed opacity-60",
        "focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/30"
      )}
    >
      <UploadCloud
        className={clsx("h-8 w-8", dragActive ? "text-brand" : "text-ink-dim")}
        aria-hidden="true"
      />
      <p className="text-sm font-medium text-ink">{prompt}</p>
      <p className="text-xs text-ink-dim">{hint}</p>
      <input
        ref={inputRef}
        id={inputId}
        type="file"
        accept={accept}
        disabled={disabled}
        aria-label={prompt}
        className="sr-only"
        onChange={(e) => {
          const selected = e.target.files?.[0] ?? null;
          onFileSelected(selected);
          e.target.value = "";
        }}
      />
    </div>
  );
}
