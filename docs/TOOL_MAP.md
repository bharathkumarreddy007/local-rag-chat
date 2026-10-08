# Open-source AI platform tool map

Project: a local internal-document Q&A assistant. The table below covers the Week 2 assignment's tools; it is a compact Markdown reference, not a rendered one-page PDF submission.

| Tool | Category / main purpose | Used for | Lab / prototype / enterprise review | Risk to consider |
|---|---|---|---|---|
| Ollama | Local model runtime | Development, local inference, model comparison | Lab / prototype; review for enterprise | Model provenance and license, endpoint exposure, memory and local data |
| Open WebUI | Self-hosted chat interface | Demos and prompt testing | Lab / prototype; review license and deployment | Accounts, stored chats, uploads, endpoint configuration; current branding conditions |
| LangChain | Workflow and RAG components | Development | Prototype / enterprise review | Data flow, tracing, integrations, tool permissions |
| LlamaIndex | Ingestion and retrieval framework | Development | Prototype / enterprise review | Document permissions, ingestion connectors, source provenance |
| Chroma | Vector database | Small local RAG projects | Lab / prototype; deployment review | Sensitive text/embeddings, persistence, deletion, shared access |
| Qdrant | Vector search service | Larger RAG prototypes | Prototype / enterprise review | API access, network exposure, stored vectors and backups |
| Milvus | Scalable vector database | Larger-scale testing | Prototype / enterprise review | Operational complexity, authorization, governance |
| Docling | Document conversion/parsing | Ingestion experiments | Lab / prototype; parser review | Extracted hidden content, parsing accuracy, untrusted files |
| FastAPI | HTTP API framework | Development and integration | Prototype / enterprise review | Authentication must be implemented; validation, rate limits, logging |
| Streamlit | Rapid application UI | Demos and experiments | Lab / prototype | Public sharing, uploaded data, session/access boundaries |
| Gradio | Rapid model/demo UI | Demos and experiments | Lab / prototype | Public sharing links, uploads, model endpoints |
| MLflow | Experiment/evaluation tracking | Testing and evaluation | Prototype / enterprise review | Logged prompts, responses, artifacts, tracking-server access |

These tools are not inherently “enterprise ready” or “lab only.” Suitability depends on configuration, version, scale, permissions, and operational controls. Public-share demo configurations should stay out of sensitive enterprise environments.

## Architecture used in this project

- **UI:** original MIT-licensed chat interface; optional Open WebUI-compatible API.
- **API:** FastAPI, protected by a local access key.
- **Parsing:** plain-text reader and pypdf. Docling is deferred until OCR or complex layouts justify it.
- **RAG:** readable Python orchestration and LangChain text splitting. LlamaIndex is an alternative, not a second required framework.
- **Vector storage:** persistent Chroma. Qdrant and Milvus are deferred because this small corpus does not need their operational complexity.
- **Local model testing:** Ollama with Qwen3 and MiniLM embeddings.
- **Evaluation:** a small retrieval test script, with optional MLflow numeric tracking.

Flow: parse and chunk approved documents, embed locally, store text/vectors/metadata, retrieve matching passages for a question, pass those passages to a local model, and show its answer with the actual retrieved excerpts.

**Biggest concern:** a document answer can expose confidential source content to anyone able to query the index. This prototype has a single-user access key and one shared corpus. It does not implement per-user or per-document access control. Prompt instructions are not an authorization boundary.

**Before enterprise use:** confirm data approval and model license/provenance; add identity and retrieval-time permissions; secure transport/storage; isolate upload parsing; define retention and deletion; restrict logs and outbound calls; evaluate retrieval, unsupported questions, citation accuracy, prompt injection, and access isolation.

## Five-minute demonstration

1. Explain why the UI, API, model runtime, and vector store are separate layers.
2. Show the selected Qwen3 model and five indexed documents.
3. Ask about WFH and inspect the retrieved HR passages.
4. Ask about an unknown employee; check that the assistant admits missing evidence.
5. Switch to General chat and explain the difference from grounded document chat.
6. Show retrieval evaluation results after running the evaluation locally.
7. Explain the local-prototype limits and the permission controls required before enterprise use.
