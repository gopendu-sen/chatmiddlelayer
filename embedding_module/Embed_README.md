# Vector Store Generator

This repository provides a command‑line utility for building a local
vector store suitable for **retrieval‑augmented generation** (RAG)
systems.  It accepts documents from the file system, a Git
repository or an Atlassian Confluence space, converts their
contents into dense embeddings using a pluggable embedding service
and indexes them using **FAISS** – an open‑source library for
efficient similarity search and clustering of dense vectors.  FAISS
contains algorithms that search in sets of vectors of any size and
offers Python bindings for ease of use.

Vector embeddings represent unstructured data (text, images, etc.)
as points in a high‑dimensional space where similar items are
closer together【589231301807203†L8-L20】.  Such embeddings allow us to
perform semantic search over large document collections, a key
component of RAG pipelines.

## Features

- **Multiple input sources**: process plain files/directories, clone
  a Git repository, or fetch pages from a Confluence space.
- **Extensible parser architecture**: a factory pattern selects
  the appropriate parser based on file extension.  Adding support
  for new formats requires implementing a new parser class
  without changing existing code【705524173246349†L27-L34】.
- **Batch embeddings**: documents are sent to a configurable
  embedding endpoint in batches to respect API limits.
- **Rich metadata**: each document retains metadata such as file
  path, page number, sheet name or Confluence page id.  Session
  identifiers are also supported.
- **FAISS vector store**: embeddings are indexed using
  `faiss.IndexFlatL2` wrapped with an ID map.  Both the index and
  metadata are persisted to disk.  If the target directory name
  already exists, a random suffix is appended to avoid
  collisions.
- **Verbose logging**: the application logs all major steps,
  including cloning, parsing, embedding requests and index
  persistence.  Logs are written to a file inside the output
  directory and to the console.

## Installation

Create a Python virtual environment (optional) and install the
dependencies:

```bash
pip install -r requirements.txt
```

Some components are optional.  For Git repository processing install
`gitpython`, and for Confluence support install
`atlassian-python-api` and `beautifulsoup4`.  If you plan to parse
PDFs you must install `PyPDF2`.

### Easy installation (step by step)

These steps are written for non-technical users.

1. Install Python 3.10+ from https://www.python.org/downloads/ (check “Add Python to PATH” during setup).
2. Install Git from https://git-scm.com/downloads (keep defaults).
3. (Windows) If you will extract text from images, install Tesseract OCR from https://github.com/UB-Mannheim/tesseract/wiki and note the install path (for example `C:\Program Files\Tesseract-OCR`).
4. Download this project (Git clone or zip download and extract).
5. Open a terminal (Command Prompt on Windows, Terminal on macOS/Linux) and change into the project folder.
6. Create or activate your Python virtual environment, then run:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
7. (Windows, OCR only) Add Tesseract to your PATH for the current terminal session:
   ```bat
   set "PATH=C:\Program Files\Tesseract-OCR;%PATH%"
   ```
8. Run the CLI command shown in the Usage section below.

### One-click setup for Windows

If your Python virtual environment lives at `C:\user\public\python_env`, run the provided batch file:

```
setup_env.bat
```

What it does:
- Activates the environment at `C:\user\public\python_env`
- Upgrades `pip`
- Installs everything from `requirements.txt`
- Temporarily adds a common Tesseract path to `PATH` (edit the path in the script if Tesseract is installed elsewhere)

## Using the code in your own Python functions

The CLI orchestrates everything, but you can call the pieces directly:

```python
from embedding_app.cli import collect_documents, run_pipeline
from embedding_app.config import AppConfig, EmbeddingConfig

cfg = AppConfig(
    vector_store_path="./stores",
    vector_store_name="my_store",
    files_location="./docs",
    embedding_config=EmbeddingConfig(endpoint="http://localhost:8001/v1/embeddings"),
)

# Just collect documents
docs = collect_documents(cfg)

# Or run the full pipeline (returns final store name)
store_name = run_pipeline(cfg)
```

You can also import lower-level components (`ParserFactory`, `EmbeddingClient`, `VectorStoreBuilder`) if you need custom flows (e.g., supply your own documents or embeddings).

## Exposing as an API service

Wrap `run_pipeline` in a lightweight web server (e.g., FastAPI or Flask) to trigger jobs over HTTP. Example with FastAPI:

```python
from fastapi import FastAPI
from pydantic import BaseModel
from embedding_app.cli import run_pipeline
from embedding_app.config import AppConfig, EmbeddingConfig, GitSettings, ConfluenceSettings

app = FastAPI()

class PipelineRequest(BaseModel):
    vector_store_path: str
    vector_store_name: str
    files_location: str | None = None
    git_url: str | None = None
    confluence_url: str | None = None
    confluence_user: str | None = None
    confluence_token: str | None = None
    confluence_space_key: str | None = None

@app.post("/run")
def run(req: PipelineRequest):
    git_cfg = GitSettings(url=req.git_url) if req.git_url else None
    conf_cfg = (
        ConfluenceSettings(
            url=req.confluence_url,
            user=req.confluence_user,
            token=req.confluence_token,
            space_key=req.confluence_space_key,
        )
        if req.confluence_url and req.confluence_user and req.confluence_token and req.confluence_space_key
        else None
    )
    cfg = AppConfig(
        vector_store_path=req.vector_store_path,
        vector_store_name=req.vector_store_name,
        files_location=req.files_location,
        git_settings=git_cfg,
        confluence_settings=conf_cfg,
        embedding_config=EmbeddingConfig(),
    )
    store_name = run_pipeline(cfg)
    return {"store_name": store_name}
```

Ensure your embedding endpoint is reachable from the server process and that any required credentials (Git/Confluence) are supplied in the request. For production, add authentication, input validation, logging, and background task management for long-running jobs.

## Usage

The utility is invoked from the command line.  The only required
arguments are the location where the vector store will be written and
its desired name.  At least one of the `--files_location`,
`--git_settings` or `--confluence_settings` flags must be provided.

```bash
python -m embedding_app.cli \
  --vector_store_path ./stores \
  --vector_store_name my_store \
  --files_location ./documents \
  --git_settings '{"url": "https://github.com/example/repo.git", "exclude_extensions": [".jpg", ".png"], "max_files": 100}' \
  --confluence_settings '{"url": "https://example.atlassian.net", "user": "email@example.com", "token": "MYTOKEN", "space_key": "DOC", "max_pages": 20}' \
  --embedding_config '{"endpoint": "http://localhost:8001/v1/embeddings", "batch_size": 32}' \
  --session_id mysession
```

After the program completes it reports the name of the created vector
store directory.  Two files will be present inside that directory:

* `index.faiss` – the FAISS index containing the vectors.
* `metadata.json` – a JSON array of objects, one per document,
  storing the document text and metadata required for retrieval.

Logs are written to `application.log` in the same directory.

## Architecture

The code is organised into several modules for clarity and
extensibility:

| Module | Responsibility |
|-------|---------------|
| `embedding_app/document.py` | Defines a `Document` dataclass capturing text and metadata. |
| `embedding_app/config.py` | Holds configuration data structures for Git, Confluence, embeddings and overall app settings. |
| `embedding_app/utils.py` | Helper functions for logging, random suffix generation and file listing. |
| `embedding_app/parsers` | Contains individual parsers for different file formats (text, CSV, Excel, PDF).  Each parser implements a `parse()` method returning one or more Documents. |
| `embedding_app/factory.py` | Implements the factory method pattern to choose a parser based on file extension【705524173246349†L27-L34】. |
| `embedding_app/git_parser.py` | Clones a Git repository and yields documents from supported files. |
| `embedding_app/confluence_parser.py` | Connects to Confluence, fetches pages and converts them to documents. |
| `embedding_app/embedding_client.py` | Sends text to the embedding endpoint in batches and returns vectors. |
| `embedding_app/vector_store.py` | Builds a FAISS index from embeddings and persists both the index and metadata. |
| `embedding_app/cli.py` | Parses command line arguments, orchestrates the pipeline and writes logs. |

## Development Notes

* **Extending parsers**: To add support for a new file type
  implement a subclass of `DocumentParser` in `embedding_app/parsers`.
  Register its extension(s) in `ParserFactory._parsers`.  Follow
  existing implementations for guidance.
* **Embedding service**: The default embedding endpoint is
  `http://localhost:8001/v1/embeddings`.  It should accept a JSON
  payload with an `input` array and return a JSON response with a
  `data` array containing embeddings.  Set `--embedding_config`
  accordingly to override the endpoint or batch size.
* **Vector index type**: The current implementation uses
  `faiss.IndexFlatL2` for exact Euclidean search.  To trade off
  search speed and accuracy you can modify
  `VectorStoreBuilder.build()` to use other FAISS index types such
  as `IndexHNSWFlat` or `IndexIVFFlat`.

## Adding a new parser

1. **Create the parser class** in `embedding_app/parsers/` as a subclass of `DocumentParser`.  Implement `parse(file_path: str) -> List[Document]` and log failures while returning an empty list on error.
2. **Handle optional dependencies** inside the parser with `try/except ImportError`, logging a clear installation hint.  Add any new libraries to `requirements.txt`.
3. **Register the parser** by importing it in `embedding_app/parsers/__init__.py` and mapping its file extension(s) in `ParserFactory._parsers` within `embedding_app/factory.py`.
4. **Populate metadata** such as `file_path`, page numbers or sheet names in the `Document.metadata` so retrieved results can be traced back to their source.
5. **Test locally** by running the CLI against sample files of the new type to ensure documents are produced and embeddings are created without errors.

## Requirements

See `requirements.txt` for a full list of dependencies.  At
minimum you will need `faiss-cpu`, `requests`, `pandas` and
`numpy`.  Optional dependencies include `gitpython`,
`atlassian-python-api`, `beautifulsoup4` and `PyPDF2`.
