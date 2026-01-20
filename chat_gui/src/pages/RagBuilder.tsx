import { FormEvent, useEffect, useMemo, useState } from "react";
import { buildVectorStoreFromPath, buildVectorStoreWithUpload } from "../lib/api";
import { SourceType } from "../lib/types";

interface Props {
  sessionId: string;
  onSessionChange: (id: string) => void;
  onStoreCreated: (path: string) => void;
}

export default function RagBuilder({ sessionId, onSessionChange, onStoreCreated }: Props) {
  const [sourceType, setSourceType] = useState<SourceType>("upload");
  const [vectorStorePath, setVectorStorePath] = useState("./stores");
  const [vectorStoreName, setVectorStoreName] = useState("td_store");
  const [filesLocation, setFilesLocation] = useState("./documents");
  const [files, setFiles] = useState<FileList | null>(null);
  const [gitUrl, setGitUrl] = useState("");
  const [gitBranch, setGitBranch] = useState("");
  const [confluenceUrl, setConfluenceUrl] = useState("");
  const [confluenceUser, setConfluenceUser] = useState("");
  const [confluenceToken, setConfluenceToken] = useState("");
  const [confluenceSpace, setConfluenceSpace] = useState("");
  const [session, setSession] = useState(sessionId);
  const [embeddingEndpoint, setEmbeddingEndpoint] = useState("http://localhost:8001/v1/embeddings");
  const [batchSize, setBatchSize] = useState(32);
  const [status, setStatus] = useState("Ready to build");
  const [building, setBuilding] = useState(false);
  const [lastPath, setLastPath] = useState("");

  const uploadLabel = useMemo(() => {
    switch (sourceType) {
      case "upload":
        return "Upload and index files";
      case "git":
        return "Index a Git repository";
      case "confluence":
        return "Index a Confluence space";
      default:
        return "Index a local folder";
    }
  }, [sourceType]);

  useEffect(() => {
    setSession(sessionId);
  }, [sessionId]);

  const handleBuild = async (evt?: FormEvent) => {
    evt?.preventDefault();
    setBuilding(true);
    setStatus("Submitting build job…");
    try {
      if (sourceType === "upload") {
        if (!files || files.length === 0) {
          throw new Error("Attach at least one file.");
        }
        const form = new FormData();
        form.append("vector_store_path", vectorStorePath);
        form.append("vector_store_name", vectorStoreName);
        form.append("session_id", session);
        form.append("embedding_endpoint", embeddingEndpoint);
        form.append("embedding_batch_size", batchSize.toString());
        Array.from(files).forEach((file) => form.append("files", file));
        const result = await buildVectorStoreWithUpload(form);
        setLastPath(result.path);
        onStoreCreated(result.path);
        setStatus(`Built store ${result.store_name}`);
      } else {
        const payload: any = {
          vector_store_path: vectorStorePath,
          vector_store_name: vectorStoreName,
          session_id: session,
          embedding_config: { endpoint: embeddingEndpoint, batch_size: batchSize },
        };

        if (sourceType === "local_path") {
          payload.files_location = filesLocation;
        } else if (sourceType === "git") {
          payload.git_settings = { url: gitUrl, branch: gitBranch || undefined };
        } else if (sourceType === "confluence") {
          payload.confluence_settings = {
            url: confluenceUrl,
            user: confluenceUser,
            token: confluenceToken,
            space_key: confluenceSpace,
          };
        }

        const result = await buildVectorStoreFromPath(payload);
        setLastPath(result.path);
        onStoreCreated(result.path);
        setStatus(`Built store ${result.store_name}`);
      }
    } catch (error: any) {
      setStatus(error?.message || "Failed to build");
    } finally {
      setBuilding(false);
    }
  };

  return (
    <div className="grid" style={{ gap: 20 }}>
      <section className="hero">
        <div className="card">
          <div className="headline">{uploadLabel}</div>
          <p className="subhead">
            Build FAISS vector stores with audit-friendly session ids. Supports local uploads, directories, Git, or
            Confluence pulls.
          </p>
          <div className="chip-row" style={{ marginTop: 10 }}>
            {(["upload", "local_path", "git", "confluence"] as SourceType[]).map((type) => (
              <button
                key={type}
                className={`button secondary${sourceType === type ? " active" : ""}`}
                type="button"
                onClick={() => setSourceType(type)}
              >
                {type === "upload" && "Upload"}
                {type === "local_path" && "Folder"}
                {type === "git" && "Git"}
                {type === "confluence" && "Confluence"}
              </button>
            ))}
          </div>
        </div>
        <div className="card">
          <div className="section-title">Build status</div>
          <div className="status">
            <div>{status}</div>
            {lastPath && (
              <div>
                Latest store path:
                <div className="chip">{lastPath}</div>
              </div>
            )}
          </div>
        </div>
      </section>

      <section className="card">
        <form className="grid two" style={{ gap: 16 }} onSubmit={handleBuild}>
          <div className="card">
            <div className="section-title">General</div>
            <label className="label" htmlFor="vector-store-name">
              Vector store name
            </label>
            <input
              id="vector-store-name"
              className="input"
              value={vectorStoreName}
              onChange={(e) => setVectorStoreName(e.target.value)}
              required
            />
            <label className="label" htmlFor="vector-store-path">
              Base path
            </label>
            <input
              id="vector-store-path"
              className="input"
              value={vectorStorePath}
              onChange={(e) => setVectorStorePath(e.target.value)}
              required
            />
            <label className="label" htmlFor="session-id">
              Session id
            </label>
            <input
              id="session-id"
              className="input"
              value={session}
              onChange={(e) => {
                setSession(e.target.value);
                onSessionChange(e.target.value);
              }}
              required
            />
            <div className="grid two" style={{ marginTop: 10 }}>
              <div>
                <label className="label" htmlFor="embedding-endpoint">
                  Embedding endpoint
                </label>
                <input
                  id="embedding-endpoint"
                  className="input"
                  value={embeddingEndpoint}
                  onChange={(e) => setEmbeddingEndpoint(e.target.value)}
                />
              </div>
              <div>
                <label className="label" htmlFor="batch-size">
                  Batch size
                </label>
                <input
                  id="batch-size"
                  className="input"
                  type="number"
                  min={1}
                  value={batchSize}
                  onChange={(e) => setBatchSize(parseInt(e.target.value, 10) || 1)}
                />
              </div>
            </div>
          </div>

          <div className="card">
            <div className="section-title">Source</div>
            {sourceType === "upload" && (
              <>
                <label className="label" htmlFor="file-upload">
                  Upload files
                </label>
                <input
                  id="file-upload"
                  className="input"
                  type="file"
                  multiple
                  onChange={(e) => setFiles(e.target.files)}
                />
                <div className="muted">
                  Files are staged under <code>{vectorStorePath}/_uploads</code> before embedding.
                </div>
              </>
            )}
            {sourceType === "local_path" && (
              <>
                <label className="label" htmlFor="files-location">
                  Folder to index
                </label>
                <input
                  id="files-location"
                  className="input"
                  value={filesLocation}
                  onChange={(e) => setFilesLocation(e.target.value)}
                />
              </>
            )}
            {sourceType === "git" && (
              <>
                <label className="label" htmlFor="git-url">
                  Git URL
                </label>
                <input id="git-url" className="input" value={gitUrl} onChange={(e) => setGitUrl(e.target.value)} />
                <label className="label" htmlFor="git-branch">
                  Branch (optional)
                </label>
                <input
                  id="git-branch"
                  className="input"
                  value={gitBranch}
                  onChange={(e) => setGitBranch(e.target.value)}
                />
              </>
            )}
            {sourceType === "confluence" && (
              <>
                <label className="label" htmlFor="conf-url">
                  Confluence URL
                </label>
                <input
                  id="conf-url"
                  className="input"
                  value={confluenceUrl}
                  onChange={(e) => setConfluenceUrl(e.target.value)}
                />
                <label className="label" htmlFor="conf-user">
                  User
                </label>
                <input
                  id="conf-user"
                  className="input"
                  value={confluenceUser}
                  onChange={(e) => setConfluenceUser(e.target.value)}
                />
                <label className="label" htmlFor="conf-token">
                  Token
                </label>
                <input
                  id="conf-token"
                  className="input"
                  type="password"
                  value={confluenceToken}
                  onChange={(e) => setConfluenceToken(e.target.value)}
                />
                <label className="label" htmlFor="conf-space">
                  Space key
                </label>
                <input
                  id="conf-space"
                  className="input"
                  value={confluenceSpace}
                  onChange={(e) => setConfluenceSpace(e.target.value)}
                />
              </>
            )}
          </div>
        </form>
        <div style={{ marginTop: 12, display: "flex", gap: 10, alignItems: "center" }}>
          <button className="button" onClick={() => handleBuild()} disabled={building}>
            {building ? "Building…" : "Build vector store"}
          </button>
          <span className="muted">Calls /vector-store/build or /vector-store/build/upload depending on source.</span>
        </div>
      </section>
    </div>
  );
}
