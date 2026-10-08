"""Single-user local chatbot. Run one worker because Chroma is embedded."""
import asyncio
from contextlib import asynccontextmanager
import hmac
import json
import os
from pathlib import Path
import time
import uuid

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import httpx
from pydantic import BaseModel, Field
from typing import Literal
from .rag import RagStore, MAX_BYTES, rag_messages

load_dotenv()
ROOT = Path(__file__).resolve().parent.parent
OLLAMA_URL = os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434').rstrip('/')
DEFAULT_MODEL = os.getenv('CHAT_MODEL', 'qwen3:4b')
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'all-minilm:latest')
API_KEY = os.getenv('RAG_API_KEY', '')
DATA_DIR = Path(os.getenv('DATA_DIR', str(ROOT / 'data')))
MAX_DISTANCE = float(os.getenv('MAX_DISTANCE', '0.9'))
store = None


@asynccontextmanager
async def lifespan(app):
    global store
    if len(API_KEY) < 24:
        raise RuntimeError('Run python scripts/setup.py first; RAG_API_KEY must contain at least 24 characters.')
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    store = RagStore(str(DATA_DIR / 'chroma'), OLLAMA_URL, EMBEDDING_MODEL)
    yield


app = FastAPI(title='Local RAG Chat', lifespan=lifespan)
app.mount('/static', StaticFiles(directory=ROOT / 'app/static'), name='static')


@app.middleware('http')
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
    response.headers['Cache-Control'] = 'no-store'
    return response


def authorize(authorization: str = Header(default='')):
    expected = 'Bearer ' + API_KEY
    if not API_KEY or not hmac.compare_digest(authorization.encode('utf-8'), expected.encode('utf-8')):
        raise HTTPException(401, 'Enter the access key from your .env file.')


@app.get('/')
def home():
    return FileResponse(ROOT / 'app/static/index.html')


@app.get('/health')
def health():
    return {'status': 'ok'}


async def available_models():
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(OLLAMA_URL + '/api/tags')
            response.raise_for_status()
            models = response.json().get('models', [])
            return [m['name'] for m in models if 'bert' not in m.get('details', {}).get('family', '').lower()
                    and m['name'] != EMBEDDING_MODEL and not m['name'].startswith(('all-minilm', 'nomic-embed', 'mxbai-embed'))]
    except (httpx.HTTPError, ValueError, KeyError):
        raise HTTPException(503, 'Ollama is unavailable. Start Ollama and download a chat model.')


@app.get('/api/status', dependencies=[Depends(authorize)])
async def status():
    models = await available_models()
    return {'models': models, 'default_model': DEFAULT_MODEL, 'embedding_model': EMBEDDING_MODEL,
            'documents': await asyncio.to_thread(store.documents)}


@app.get('/api/documents', dependencies=[Depends(authorize)])
async def documents():
    return await asyncio.to_thread(store.documents)


@app.post('/api/documents', dependencies=[Depends(authorize)])
async def upload(file: UploadFile = File(...)):
    content = await file.read(MAX_BYTES + 1)
    await file.close()
    try:
        return await asyncio.to_thread(store.ingest, file.filename or '', content)
    except (ValueError, UnicodeError):
        raise HTTPException(400, 'Could not index this file. Use a UTF-8 TXT/MD or text PDF under 5 MB, 100 pages, and 500,000 characters.')
    except httpx.HTTPError:
        raise HTTPException(503, 'Embedding failed. Confirm the embedding model is downloaded; an oversized chunk may also exceed its context limit.')
    except Exception:
        raise HTTPException(400, 'Document could not be parsed or indexed. Check its format and try again.')


@app.delete('/api/documents/{name}', dependencies=[Depends(authorize)])
async def delete_document(name: str):
    await asyncio.to_thread(store.delete, name)
    return {'deleted': name}


@app.post('/api/index-seed', dependencies=[Depends(authorize)])
async def index_seed():
    results = []
    for path in sorted((DATA_DIR / 'documents').glob('*.txt')):
        try:
            results.append(await asyncio.to_thread(store.ingest, path.name, path.read_bytes()))
        except Exception:
            results.append({'name': path.name, 'status': 'failed', 'error': 'Check Ollama, embedding model, and input format.'})
    return {'documents': results}


class Message(BaseModel):
    role: Literal['user', 'assistant']
    content: str = Field(max_length=12000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    model: str = Field(default=DEFAULT_MODEL, max_length=120)
    mode: Literal['rag', 'chat'] = 'rag'
    history: list[Message] = Field(default_factory=list, max_length=20)
    top_k: int = Field(default=5, ge=1, le=10)


async def prepare_chat(body: ChatRequest):
    if not body.question.strip():
        raise HTTPException(422, 'Write a question first.')
    if body.model not in await available_models():
        raise HTTPException(400, 'Selected model is not installed. Download it with Ollama first.')
    history = [m.model_dump() for m in body.history[-10:]]
    sources = []
    if body.mode == 'rag':
        # Include the latest user turn for follow-up queries without embedding a long answer.
        previous = next((m['content'] for m in reversed(history) if m['role'] == 'user'), '')
        query = (previous[:600] + '\n' + body.question) if previous else body.question
        # Bound query length for the small embedding model; generation still sees the full question.
        try:
            sources = await asyncio.to_thread(store.retrieve, query[-700:], body.top_k, MAX_DISTANCE)
        except httpx.HTTPError:
            raise HTTPException(503, 'Retrieval failed. Confirm Ollama and the embedding model are running.')
        messages = rag_messages(body.question, sources, history)
    else:
        messages = [{'role': 'system', 'content': 'You are a helpful assistant. Be clear about uncertainty.'},
                    *history, {'role': 'user', 'content': body.question}]
    return messages, sources


def ollama_payload(model, messages, stream):
    payload = {'model': model, 'messages': messages, 'stream': stream,
               'options': {'temperature': 0.2, 'num_ctx': 8192, 'num_predict': 2048}}
    if model.startswith('qwen3:'):
        payload['think'] = False
    return payload


NO_EVIDENCE = 'I could not find that information in the indexed documents. Add relevant documents or switch to General chat.'


@app.post('/api/chat', dependencies=[Depends(authorize)])
async def chat(body: ChatRequest):
    messages, sources = await prepare_chat(body)
    async def generate():
        yield json.dumps({'type': 'sources', 'sources': sources}) + '\n'
        if body.mode == 'rag' and not sources:
            yield json.dumps({'type': 'token', 'text': NO_EVIDENCE}) + '\n'
            yield json.dumps({'type': 'done'}) + '\n'
            return
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=10)) as client:
                async with client.stream('POST', OLLAMA_URL + '/api/chat',
                        json=ollama_payload(body.model, messages, True)) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        event = json.loads(line)
                        if event.get('error'):
                            raise ValueError('Model error')
                        token = event.get('message', {}).get('content', '')
                        if token:
                            yield json.dumps({'type': 'token', 'text': token}) + '\n'
            yield json.dumps({'type': 'done'}) + '\n'
        except (httpx.HTTPError, ValueError):
            yield json.dumps({'type': 'error', 'message': 'Generation failed. Check Ollama, model memory requirements, and try again.'}) + '\n'
    return StreamingResponse(generate(), media_type='application/x-ndjson')


@app.post('/api/retrieve', dependencies=[Depends(authorize)])
async def retrieve(body: ChatRequest):
    try:
        return {'sources': await asyncio.to_thread(store.retrieve, body.question[-700:], body.top_k, MAX_DISTANCE)}
    except httpx.HTTPError:
        raise HTTPException(503, 'Embedding model unavailable.')


# Optional interoperability: Open WebUI can connect to /v1 with the same API key.
@app.get('/v1/models', dependencies=[Depends(authorize)])
async def models():
    return {'object': 'list', 'data': [{'id': 'rag/' + m, 'object': 'model', 'owned_by': 'local'} for m in await available_models()]}


class CompatibleRequest(BaseModel):
    model: str
    messages: list[dict] = Field(min_length=1, max_length=22)
    stream: bool = False


@app.post('/v1/chat/completions', dependencies=[Depends(authorize)])
async def compatible_chat(body: CompatibleRequest):
    if body.messages[-1].get('role') != 'user' or not isinstance(body.messages[-1].get('content'), str):
        raise HTTPException(400, 'The final message must be a text user question. Images and tools are not supported.')
    try:
        request = ChatRequest(question=body.messages[-1]['content'], model=body.model.removeprefix('rag/'),
            history=[Message(**m) for m in body.messages[:-1] if m.get('role') in {'user', 'assistant'}][-20:])
    except ValueError:
        raise HTTPException(400, 'Invalid or oversized text message.')
    messages, sources = await prepare_chat(request)
    answer = NO_EVIDENCE
    if sources:
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                response = await client.post(OLLAMA_URL + '/api/chat', json=ollama_payload(request.model, messages, False))
                response.raise_for_status()
                answer = response.json()['message']['content']
        except (httpx.HTTPError, KeyError, ValueError):
            raise HTTPException(503, 'Local model generation failed.')
        answer += '\n\nRetrieved sources:\n' + '\n'.join(f"[{s['id']}] {s['source']} — chunk {s['chunk']}" for s in sources)
    ident = 'chatcmpl-' + uuid.uuid4().hex
    base = {'id': ident, 'created': int(time.time()), 'model': body.model}
    if body.stream:
        async def events():
            yield 'data: ' + json.dumps({**base, 'object': 'chat.completion.chunk', 'choices': [{'index': 0, 'delta': {'role': 'assistant', 'content': answer}, 'finish_reason': None}]}) + '\n\n'
            yield 'data: ' + json.dumps({**base, 'object': 'chat.completion.chunk', 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]}) + '\n\n'
            yield 'data: [DONE]\n\n'
        return StreamingResponse(events(), media_type='text/event-stream')
    return {**base, 'object': 'chat.completion', 'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': answer}, 'finish_reason': 'stop'}]}
