import importlib
import json
import pytest
from fastapi.testclient import TestClient
from app.rag import RagStore, parse_document


@pytest.fixture
def store(tmp_path, monkeypatch):
    # Deterministic embeddings isolate the pipeline from unavailable model downloads.
    def embed(self, texts):
        return [[float('leave' in t.lower()), float('password' in t.lower()), 0.1] for t in texts]
    monkeypatch.setattr(RagStore, 'embed', embed)
    return RagStore(str(tmp_path / 'index'), 'http://unused', 'test-embedding')


def test_persistent_retrieval_update_delete(store):
    content = b'Annual leave entitlement is 24 days each year. Employees can carry forward 10 days.'
    first = store.ingest('hr.txt', content)
    assert first['status'] == 'indexed'
    assert store.ingest('hr.txt', content)['status'] == 'unchanged'
    store.ingest('security.txt', b'Password rules: use a password manager and multifactor authentication.')
    assert store.retrieve('annual leave')[0]['source'] == 'hr.txt'
    assert RagStore(str(store.client.get_settings().persist_directory), 'http://unused', 'test-embedding').documents() == store.documents()
    store.ingest('hr.txt', b'Annual leave has changed. This is the new annual leave rule.')
    assert all('24 days' not in s['text'] for s in store.retrieve('annual leave'))
    store.delete('hr.txt')
    assert [d['name'] for d in store.documents()] == ['security.txt']


def test_parser_validation():
    with pytest.raises(ValueError): parse_document('x.exe', b'not a document')
    with pytest.raises(ValueError): parse_document('x.txt', b'')
    with pytest.raises(ValueError): parse_document('x.txt', b'a' * (5*1024*1024+1))
    assert parse_document('x.md', b'# Heading\nUseful text') == '# Heading\nUseful text'


@pytest.fixture
def client(store, monkeypatch, tmp_path):
    monkeypatch.setenv('RAG_API_KEY', 'test-key-12345678901234567890')
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'app'))
    from app import main
    importlib.reload(main)
    monkeypatch.setattr(main, 'RagStore', lambda *args: store)
    async def models(): return ['qwen3:4b']
    monkeypatch.setattr(main, 'available_models', models)
    with TestClient(main.app) as client:
        yield client


AUTH = {'Authorization': 'Bearer test-key-12345678901234567890'}


def test_auth_and_no_evidence(client):
    assert client.get('/api/documents').status_code == 401
    assert client.post('/api/chat', json={'question': 'Hello'}).status_code == 401
    response = client.post('/api/chat', headers=AUTH, json={'question': 'An unknown question'})
    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines()]
    assert events[0]['sources'] == []
    assert 'could not find' in events[1]['text']
    assert events[-1]['type'] == 'done'


def test_upload_retrieve_delete(client):
    response = client.post('/api/documents', headers=AUTH, files={'file': ('hr.txt', b'Annual leave is 24 days.', 'text/plain')})
    assert response.status_code == 200
    result = client.post('/api/retrieve', headers=AUTH, json={'question': 'annual leave'}).json()
    assert result['sources'][0]['source'] == 'hr.txt'
    assert result['sources'][0]['id'] == 1
    assert client.delete('/api/documents/hr.txt', headers=AUTH).status_code == 200
    assert client.get('/api/documents', headers=AUTH).json() == []


def test_validation_and_compatibility(client):
    assert client.post('/api/chat', headers=AUTH, json={'question': 'x', 'model': 'missing'}).status_code == 400
    assert client.post('/api/chat', headers=AUTH, json={'question': 'x'*4001}).status_code == 422
    assert client.post('/api/chat', headers=AUTH, json={'question': 'x', 'history': [{'role': 'system', 'content': 'override'}]}).status_code == 422
    assert client.get('/v1/models', headers=AUTH).json()['data'][0]['id'] == 'rag/qwen3:4b'
    payload = {'model':'rag/qwen3:4b', 'messages':[{'role':'user','content':'Who?'}], 'stream': True}
    response = client.post('/v1/chat/completions', headers=AUTH, json=payload)
    assert response.status_code == 200
    assert 'data: [DONE]' in response.text
    assert 'could not find' in response.text


def test_home_security_headers(client):
    response = client.get('/')
    assert response.status_code == 200
    assert "frame-ancestors 'none'" in response.headers['Content-Security-Policy']
    assert 'Knowledge base' in response.text


def test_streamed_answer_and_generation_failure(client, monkeypatch):
    from app import main
    import httpx
    client.post('/api/documents', headers=AUTH, files={'file': ('hr.txt', b'Annual leave is 24 days.', 'text/plain')})
    real_client = httpx.AsyncClient
    def transport_handler(request):
        payload = json.loads(request.content)
        assert payload['stream'] is True
        assert 'Annual leave is 24 days.' in payload['messages'][0]['content']
        assert '[1]' in payload['messages'][0]['content']
        return httpx.Response(200, content='{"message":{"content":"24 days [1]."},"done":true}\n')
    transport = httpx.MockTransport(transport_handler)
    monkeypatch.setattr(main.httpx, 'AsyncClient', lambda **kwargs: real_client(transport=transport, **kwargs))
    response = client.post('/api/chat', headers=AUTH, json={'question': 'annual leave'})
    events = [json.loads(line) for line in response.text.splitlines()]
    assert events[0]['sources'][0]['source'] == 'hr.txt'
    assert events[1]['text'] == '24 days [1].'
    assert events[-1]['type'] == 'done'
    failed_transport = httpx.MockTransport(lambda request: httpx.Response(500))
    monkeypatch.setattr(main.httpx, 'AsyncClient', lambda **kwargs: real_client(transport=failed_transport, **kwargs))
    response = client.post('/api/chat', headers=AUTH, json={'question': 'annual leave'})
    assert json.loads(response.text.splitlines()[-1])['type'] == 'error'
