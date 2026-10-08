# Local RAG Chat

A ChatGPT-style local chatbot built around your RAG notebook and five supplied company documents. It provides general chat, document Q&A, model selection, streaming, browser-local chat history, Markdown exports, uploads, persistent retrieval, and expandable source excerpts.

**This is a runnable single-user learning/prototype project, not a production enterprise platform or a replica of every ChatGPT feature.** No paid AI API key is required. Model downloads need internet; normal inference and retrieval use your local Ollama service.

## 1. Start here — Docker route (Windows, macOS, Linux)

Prerequisites: Python 3.12 and a running Docker installation with Compose. On Windows/macOS, Docker Desktop is convenient but has its own licensing terms; Linux Docker Engine is an alternative. If you want to avoid Docker Desktop entirely, use the native Python route below.

1. Extract this ZIP and open a terminal inside `local-rag-chat` (the folder with `compose.yaml`).
2. Create your private configuration:

   ```sh
   python scripts/setup.py
   ```

   On Windows, `py -3.12 scripts/setup.py` also works. Do not upload or share the generated `.env` file.

3. Start the services:

   ```sh
   docker compose up -d --build
   ```

4. Download one chat model and one embedding model:

   ```sh
   docker compose exec ollama ollama pull qwen3:4b
   docker compose exec ollama ollama pull all-minilm:latest
   ```

5. Open **http://localhost:8000**. Open `.env` in a text editor and copy the value after `RAG_API_KEY=` into the app's access-key field.
6. Open **Knowledge base → Index 5 included documents**. Wait for indexing to finish. This does not happen automatically on restart, so deleted documents stay deleted until you explicitly index them again.
7. Select **Ask my documents** and ask: **“What is the work from home policy?”** Expand the retrieved passages and verify the answer.
8. Switch to **General chat** for questions outside your documents.

The first downloads/build can take several minutes. The UI can start before Ollama finishes starting; if connection fails, wait briefly and press **Connect** again.

### Stop and restart

```sh
docker compose down
docker compose up -d
```

These preserve model and index volumes. **Do not add `-v` unless you intentionally want to delete the stored models and index.** Chats are stored separately in your browser and can be cleared through Settings.

### Hardware starting point

Try `qwen3:4b` on a machine with roughly 16 GB system RAM and sufficient free disk space (allow at least 15 GB for containers, packages, and models). These are planning estimates, not guaranteed minimums. CPU inference works but can be slow; GPU acceleration is optional and is not configured by the default Compose file. On a smaller machine, try `qwen3:0.6b`; it is lighter but may give weaker answers and citations. Larger context windows and models increase memory use.

## 2. Native Python route (without Docker)

Install Python 3.12 and Ollama from https://ollama.com/download. Run Ollama on this same machine, then:

```sh
python scripts/setup.py
python -m venv .venv
```

Activate your environment:

- Windows PowerShell: `.\.venv\Scripts\Activate.ps1`
- Windows Command Prompt: `.venv\Scripts\activate.bat`
- macOS/Linux: `source .venv/bin/activate`

Then run:

```sh
python -m pip install -r requirements.txt
ollama pull qwen3:4b
ollama pull all-minilm:latest
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

Open http://localhost:8000 and follow steps 5–8 above. The app uses `.env` automatically. Keep Ollama and the app bound to localhost. Use only one app worker because Chroma runs embedded in this process.

## What is included

| Layer | Selected tool | Reason |
|---|---|---|
| Chat UI | Original HTML/CSS/JavaScript, MIT licensed | ChatGPT-style layout without another framework or branding constraints |
| HTTP API | FastAPI | Input validation, uploads, streaming, access-key checks |
| Chat runtime | Ollama | Runs downloaded models locally |
| Starting chat model | Qwen3 4B | Apache-2.0 model weights; lighter 0.6B alternative available |
| Embeddings | Ollama `all-minilm` | Small local embedding model, related to the notebook's MiniLM approach |
| Chunking | LangChain text splitters | Bounded chunks with overlap; no agent loop |
| RAG orchestration | Small, readable Python functions | Easy to follow and modify alongside your notebook |
| Vector store | Persistent Chroma | Stores text, vectors, source names, and chunk identifiers |
| Parsing | UTF-8 reader + pypdf | Enough for your TXT files and text PDFs; no heavy OCR dependency |
| Evaluation | Included retrieval script; optional MLflow | Check source retrieval before adding complexity |

The model weights, installed packages, and your documents are not relicensed by the app's MIT license. Check each model's own license before use. Open weights does not always mean unrestricted open source. We do not preinstall “all LLMs”: this app supports Ollama-compatible **text chat** models you download and your hardware can run. Models requiring different runtimes or multimodal inputs need another adapter.

## How your RAG pipeline works

```text
Upload -> parse text -> split overlapping chunks -> local embeddings -> persistent Chroma
Question -> local embedding -> retrieve passages -> grounded prompt -> local chat model -> answer + excerpts
```

The app splits at about 600 characters with 100-character overlap. Embedding requests reject truncation so long inputs do not silently lose text. The embedding model's short context means unusually dense text or some languages may need a smaller chunk size. If changing the splitter, increment `chunks-v1` in `app/rag.py` and reindex.

Retrieval uses cosine distance, top 5 by default, with a configurable maximum distance (`MAX_DISTANCE=0.9`). This is a starting threshold, **not a calibrated probability or a guarantee of relevance**. Tune it using your test questions. With no retrieved evidence, the server refuses to generate a document answer. With weak or misleading evidence, a model can still be wrong: verify the displayed excerpts.

Each passage has a numbered reference, filename, and chunk number. The model is asked to cite `[1]`, `[2]`, etc. The UI separately shows all retrieved passages; that does not prove every passage was used or every citation is valid. PDF page-level citations are not implemented.

For follow-up questions, retrieval includes the preceding user turn; generation receives up to 10 recent messages. This is basic conversational RAG, not full query rewriting. Rephrase an ambiguous follow-up if retrieval misses it.

## Documents

Included, copied without alteration from your uploads:

- `company_hr_policy.txt`
- `engineering_standards.txt`
- `onboarding_guide.txt`
- `product_knowledge_base.txt`
- `security_policy.txt`

The assignment PDF and original notebook are not indexed as company knowledge. Their useful architecture informed this implementation, but the notebook's remote endpoint, API-key printing, and execution outputs are not copied into the project.

Upload UTF-8 TXT/MD or text-based PDF files through Knowledge base. Limits: 5 MB per file, 100 PDF pages, and 500,000 extracted characters. Scanned PDFs need OCR first. Uploads are indexed directly; original upload bytes are not retained by the API. Chroma retains extracted text, metadata, and vectors. Reuploading an identical file is idempotent; uploading new contents under the same filename replaces its indexed chunks. Duplicate filenames are therefore treated as the same document.

Removing an indexed document does not erase its original source file or previously saved chat excerpts. Delete those separately when necessary. Never treat embeddings as anonymous data.

## More models

Example:

```sh
docker compose exec ollama ollama pull qwen3:0.6b
```

For a native installation use `ollama pull qwen3:0.6b`. Reconnect in Settings to refresh the model selector. Change `CHAT_MODEL` in `.env` to change the default (restart/recreate the app afterward). Model-specific features such as tools, images, audio, or reasoning formats are not implemented by this text-only client. Qwen3 thinking is disabled by default for straightforward chat.

Changing `EMBEDDING_MODEL` creates a separate Chroma collection. Reindex your documents after the change. Old collections remain on disk; changing model does not automatically erase them.

## Optional Open WebUI connection

The default interface is original MIT-licensed code. Current Open WebUI versions include additional branding conditions, so Open WebUI is **optional and not bundled**. If you already run it, retain its required branding and review its license.

In Open WebUI's Admin settings → Connections, add an OpenAI-compatible provider:

- Base URL: `http://host.docker.internal:8000/v1` if Open WebUI runs in Docker and can reach your host app. On Linux, configure the host gateway if needed. If both run on the host, use `http://127.0.0.1:8000/v1`.
- API key: your `RAG_API_KEY`.
- Model: choose a returned `rag/<model-name>` entry.

Loopback-only Docker host publishing may not be reachable from a separate container. Prefer putting Open WebUI on the same private Compose network and using `http://app:8000/v1`; do not open a public app port just to make this work. The built-in interface avoids this extra setup.

This is a small **OpenAI-compatible protocol adapter**, not a call to OpenAI. Its streaming response is buffered after local generation. Its scope is text chat; tools and images are unsupported. Upload/index documents in the built-in interface, since Open WebUI's own knowledge store is separate.

## Evaluation and tests

After the app is running and documents are indexed, install the Python requirements in a local virtual environment and run:

```sh
python scripts/evaluate.py
```

It produces `evaluation-results.json` with hit rate at 5, mean reciprocal rank at 5, and latency across six source-retrieval questions. It does not claim to measure factual correctness, faithfulness, or production readiness. For the exact test results obtained during project creation, see `docs/VALIDATION.md`.

Optional MLflow tracking:

```sh
python -m pip install mlflow-skinny
```

Set `ENABLE_MLFLOW=1` in your terminal environment and run the evaluation again. It records numeric summary metrics locally under `mlruns/`, without logging question or answer text. This optional integration is not part of the tested dependency set.

Unit/integration checks with real Chroma and controlled fake model vectors:

```sh
python -m pip install pytest
python -m pytest -q
```

Manual answer checks: WFH policy, annual leave, onboarding steps, product pricing, an unanswered question (for example, “Who is employee Z?”), and a document containing “ignore previous instructions.” Confirm factual support, abstention, and safe behavior. Do not interpret a successful test prompt as a prompt-injection guarantee.

## Data handling and prototype limits

- Default Docker host port is localhost only; Ollama has no published host port.
- Protected API endpoints require a random access key. This is single-user access control, not accounts, SSO, tenant isolation, document ACLs, or enterprise authorization.
- Chroma text/vectors remain on disk; conversations remain in browser local storage. The access key lasts in session storage. Local storage is not encrypted and is accessible to users of the same browser profile.
- The default inference path calls only the configured Ollama URL; no hosted model provider, remote tunnel, or paid API is configured. Initial package/image/model downloads require external connections. Tracing is disabled in the Docker environment and Chroma anonymized telemetry is disabled in code.
- No model-generated HTML is executed. Sources are untrusted text, and the system prompt instructs the model to treat them as data. This reduces risk but does not solve prompt injection.
- File-size/type checks exist; malware scanning, rate limiting, isolated parsing workers, backups, and comprehensive security auditing are not implemented. Use trusted files in this local prototype.
- No automatic web search, agents, code execution, fine-tuning, voice, image generation, or internet deployment is included.
- Before enterprise use: authenticated identities, per-document authorization before retrieval, TLS, encrypted storage, audit/retention policies, upload isolation, dependency/image review, evaluation, and an approved model/license inventory are needed.

## Troubleshooting

| Problem | Action |
|---|---|
| App fails with access-key error | Run `python scripts/setup.py`; ensure `.env` has a key of at least 24 characters. Recreate Compose app after changing it. |
| Ollama unavailable | Check `docker compose ps` and `docker compose logs --tail=50 ollama`. Native route: start Ollama. |
| No model in selector | Pull a chat model, then reconnect. |
| Indexing fails | Pull `all-minilm:latest`; verify file limits. Shorten chunks if embedding context is exceeded. |
| No answer in document mode | Index documents; inspect retrieval and revise the question. General questions belong in General chat. |
| Model is very slow / out of memory | Try `qwen3:0.6b`, close other applications, reduce context in `ollama_payload`, or configure supported GPU acceleration. |
| App port already in use | Change host mapping to `127.0.0.1:8001:8000`, then open port 8001. |
| Scanned PDF has no text | OCR it outside the app; Docling is an optional future parser, not installed here. |
| Browser history missing | History belongs to the browser/profile/origin; export conversations before clearing its data. |

## Source map

- `app/main.py`: API, authentication, model calls, streaming, optional compatibility adapter.
- `app/rag.py`: parsers, chunking, embeddings, persistent index, retrieval, grounded prompt.
- `app/static/`: interface, chat history, sources, upload controls.
- `compose.yaml`, `Dockerfile`: local deployment.
- `scripts/setup.py`: private configuration.
- `scripts/evaluate.py`: retrieval evaluation; optional numeric MLflow tracking.
- `tests/`: deterministic checks without model downloads.
- `docs/TOOL_MAP.md`: assignment-oriented tool comparison and architecture.

## References checked while building

- Ollama chat API: https://docs.ollama.com/api/chat
- Ollama embedding API: https://docs.ollama.com/api/embed
- Ollama model list: https://docs.ollama.com/api/tags
- Qwen3 4B: https://ollama.com/library/qwen3:4b
- Qwen3 model license: https://huggingface.co/Qwen/Qwen3-4B/blob/main/LICENSE
- MiniLM runtime model: https://ollama.com/library/all-minilm
- Chroma configuration: https://docs.trychroma.com/docs/collections/configure
- Open WebUI license: https://docs.openwebui.com/license/
"# local-rag-chat" 

<img width="1473" height="752" alt="image" src="https://github.com/user-attachments/assets/9b39910a-8d96-4924-bd39-329e0ac15df8" />
<img width="1681" height="1007" alt="image" src="https://github.com/user-attachments/assets/784dc8ab-676a-4a21-bfab-f7a86f36cf02" />
<img width="748" height="738" alt="image" src="https://github.com/user-attachments/assets/b9860d91-426a-465f-b26d-d67b43f6a741" />

