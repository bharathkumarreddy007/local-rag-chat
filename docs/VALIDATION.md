# Validation performed

## Passed

- Seven pytest checks using a real persistent Chroma index and deterministic fake embeddings/model responses.
- Document ingestion, duplicate-upload idempotency, replacement without stale chunks, persistence, deletion, and source retrieval.
- File input limits, request validation, access-key requirements, and rejection of client-injected system messages in the main chat API.
- No-evidence response, source metadata, streamed answer events, controlled model-error handling, and the optional compatibility response format.
- JavaScript syntax validation.
- Browser checks at 1440x1000 and 390x844: no page JavaScript errors or horizontal overflow; welcome prompts populate the composer.
- Browser flow with controlled API responses: connection, rendered answer, expandable source, saved-history reload, and new conversation.
- Desktop/mobile screenshots inspected for readability and layout.
- Compose YAML syntax parsed (this is not a Docker deployment test).
- All five included source files hash-match the supplied originals.

The Python HTTP test harness needed execution outside this workspace's restricted sandbox to avoid a thread/event-loop limitation. Tests passed there in under one second.

## Not verified here

- Actual Ollama inference or real MiniLM embeddings: Docker and Ollama were not available in the execution workspace.
- Full Docker build/start, model-download completion, GPU configuration, or performance on the user's computer.
- Real-model groundedness, citation accuracy, unsupported-question refusal, or numerical retrieval evaluation scores. Run scripts/evaluate.py after starting Ollama and indexing the files.
- Optional Open WebUI installation/connection or MLflow integration.
- Production security, multiple-user permissions, malware scanning, or large-document load testing.

Test stubs are confined to tests and browser validation; the shipped application requires a real Ollama service and never presents a fabricated response as model output.
