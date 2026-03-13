import { useEffect, useState, useCallback } from "react";
import { getFiles, uploadFile, deleteFile, getFileDownloadUrl, type FileObject } from "@/api";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import {
  Folder,
  FileIcon,
  FileImage,
  FileCode,
  FileText as FileTextIcon,
  Upload,
  Download,
  Trash2,
  Grid3X3,
  List,
  ChevronRight,
  HardDrive,
  X,
} from "lucide-react";

function fileIcon(name: string) {
  const ext = name.split(".").pop()?.toLowerCase() ?? "";
  if (["png", "jpg", "jpeg", "gif", "webp", "svg"].includes(ext)) return FileImage;
  if (["ts", "tsx", "js", "jsx", "py", "go", "java", "rs", "yaml", "json"].includes(ext)) return FileCode;
  if (["md", "txt", "log", "csv"].includes(ext)) return FileTextIcon;
  return FileIcon;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function isPreviewable(name: string): boolean {
  const ext = name.split(".").pop()?.toLowerCase() ?? "";
  return ["png", "jpg", "jpeg", "gif", "webp", "svg", "txt", "md", "log", "json", "yaml", "csv"].includes(ext);
}

function isImage(name: string): boolean {
  const ext = name.split(".").pop()?.toLowerCase() ?? "";
  return ["png", "jpg", "jpeg", "gif", "webp", "svg"].includes(ext);
}

export default function CloudDrive() {
  const [files, setFiles] = useState<FileObject[]>([]);
  const [prefix, setPrefix] = useState("");
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [dragging, setDragging] = useState(false);
  const [preview, setPreview] = useState<FileObject | null>(null);
  const [previewContent, setPreviewContent] = useState<string | null>(null);
  const [configured, setConfigured] = useState(true);
  const [hint, setHint] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setHint(null);
    getFiles(prefix)
      .then((r) => {
        setFiles(r.files ?? []);
        setConfigured(r.configured !== false);
        if (!r.configured) setHint(r.message ?? "MinIO not configured");
      })
      .catch(() => setHint("Failed to load files"))
      .finally(() => setLoading(false));
  }, [prefix]);

  useEffect(() => { load(); }, [load]);

  const navigate = (dir: string) => {
    setPrefix(dir);
    setPreview(null);
  };

  const breadcrumbs = prefix.split("/").filter(Boolean);

  const handleUpload = async (fileList: FileList | null) => {
    if (!fileList) return;
    for (const file of Array.from(fileList)) {
      await uploadFile(file, prefix);
    }
    load();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    handleUpload(e.dataTransfer.files);
  };

  const handleDelete = async (key: string) => {
    await deleteFile(key);
    setPreview(null);
    load();
  };

  const openPreview = async (f: FileObject) => {
    setPreview(f);
    setPreviewContent(null);
    if (!isImage(f.name) && isPreviewable(f.name)) {
      try {
        const r = await fetch(getFileDownloadUrl(f.key));
        setPreviewContent(await r.text());
      } catch {
        setPreviewContent("(Preview unavailable)");
      }
    }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Artifacts</h1>
          <p className="mt-1 text-sm text-gray-500">Agent-generated deliverables</p>
        </div>
        <div className="flex items-center gap-2">
          <label className="cursor-pointer rounded-lg bg-accent/10 px-3 py-2 text-sm font-medium text-accent transition-colors hover:bg-accent/20">
            <Upload className="inline h-3.5 w-3.5 mr-1.5" />
            Upload
            <input type="file" multiple className="hidden" onChange={(e) => handleUpload(e.target.files)} />
          </label>
          <button
            onClick={() => setViewMode(viewMode === "grid" ? "list" : "grid")}
            className="rounded-lg bg-white/[0.06] p-2 text-gray-400 hover:text-white transition-colors"
          >
            {viewMode === "grid" ? <List className="h-4 w-4" /> : <Grid3X3 className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {/* Breadcrumbs */}
      <div className="flex items-center gap-1 text-sm">
        <button onClick={() => navigate("")} className="text-gray-400 hover:text-white transition-colors">
          <HardDrive className="h-3.5 w-3.5" />
        </button>
        {breadcrumbs.map((part, i) => (
          <span key={i} className="flex items-center gap-1">
            <ChevronRight className="h-3 w-3 text-gray-600" />
            <button
              onClick={() => navigate(breadcrumbs.slice(0, i + 1).join("/") + "/")}
              className="text-gray-400 hover:text-white transition-colors"
            >
              {part}
            </button>
          </span>
        ))}
      </div>

      {hint && (
        <div className="glass-card border-amber-500/20 bg-amber-500/5 p-4 text-sm text-amber-300">{hint}</div>
      )}

      {/* Drop zone + file browser */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={cn(
          "min-h-[300px] rounded-xl border-2 border-dashed transition-colors",
          dragging ? "border-accent bg-accent/5" : "border-transparent",
        )}
      >
        {loading ? (
          <div className={cn("gap-3", viewMode === "grid" ? "grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4" : "space-y-1")}>
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className={viewMode === "grid" ? "h-28" : "h-10"} />
            ))}
          </div>
        ) : files.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-gray-600">
            <HardDrive className="h-10 w-10 mb-3" />
            <p className="text-sm">{configured ? "Empty folder. Drop files here to upload." : "MinIO not configured."}</p>
          </div>
        ) : viewMode === "grid" ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            {files.map((f) => {
              const Icon = f.isDirectory ? Folder : fileIcon(f.name);
              return (
                <div
                  key={f.key}
                  onClick={() => f.isDirectory ? navigate(f.key) : openPreview(f)}
                  className="glass-card flex flex-col items-center gap-2 p-4 cursor-pointer transition-all hover:border-border-strong"
                >
                  <Icon className={cn("h-8 w-8", f.isDirectory ? "text-accent" : "text-gray-400")} />
                  <span className="text-xs text-gray-300 text-center truncate w-full">{f.name}</span>
                  {!f.isDirectory && (
                    <span className="text-[10px] text-gray-600">{formatSize(f.size)}</span>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="space-y-0.5">
            {files.map((f) => {
              const Icon = f.isDirectory ? Folder : fileIcon(f.name);
              return (
                <div
                  key={f.key}
                  onClick={() => f.isDirectory ? navigate(f.key) : openPreview(f)}
                  className="flex items-center gap-3 rounded-lg px-3 py-2 cursor-pointer transition-colors hover:bg-white/[0.03]"
                >
                  <Icon className={cn("h-4 w-4 shrink-0", f.isDirectory ? "text-accent" : "text-gray-500")} />
                  <span className="flex-1 text-sm text-gray-300 truncate">{f.name}</span>
                  {!f.isDirectory && (
                    <span className="text-xs text-gray-600">{formatSize(f.size)}</span>
                  )}
                  {f.lastModified && !f.isDirectory && (
                    <span className="text-xs text-gray-600">{new Date(f.lastModified).toLocaleDateString()}</span>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Preview panel */}
      {preview && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setPreview(null)}>
          <div className="glass-card relative m-4 max-h-[80vh] max-w-3xl w-full overflow-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between border-b border-border px-5 py-3">
              <span className="text-sm font-medium text-white truncate">{preview.name}</span>
              <div className="flex items-center gap-2">
                <a
                  href={getFileDownloadUrl(preview.key)}
                  className="rounded-lg bg-white/[0.06] p-1.5 text-gray-400 hover:text-white transition-colors"
                  download
                >
                  <Download className="h-4 w-4" />
                </a>
                <button
                  onClick={() => handleDelete(preview.key)}
                  className="rounded-lg bg-white/[0.06] p-1.5 text-gray-400 hover:text-red-400 transition-colors"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
                <button
                  onClick={() => setPreview(null)}
                  className="rounded-lg bg-white/[0.06] p-1.5 text-gray-400 hover:text-white transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>
            <div className="p-5">
              {isImage(preview.name) ? (
                <img src={getFileDownloadUrl(preview.key)} alt={preview.name} className="mx-auto max-h-[60vh] rounded-lg" />
              ) : previewContent !== null ? (
                <pre className="text-xs text-gray-300 whitespace-pre-wrap font-mono max-h-[60vh] overflow-auto">{previewContent}</pre>
              ) : (
                <div className="py-12 text-center text-sm text-gray-600">
                  <a href={getFileDownloadUrl(preview.key)} download className="text-accent hover:underline">
                    Download to view
                  </a>
                </div>
              )}
              <div className="mt-3 flex gap-4 text-xs text-gray-600">
                <span>{formatSize(preview.size)}</span>
                {preview.lastModified && <span>{new Date(preview.lastModified).toLocaleString()}</span>}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
