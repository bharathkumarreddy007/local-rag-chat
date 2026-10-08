"""Retrieval smoke evaluation. No prompts/answers are sent to an external service."""
import json
import os
from pathlib import Path
import statistics
import time
import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')
CASES = [
    ('How many days of annual leave do employees receive?', 'company_hr_policy.txt'),
    ('What are the work from home rules?', 'company_hr_policy.txt'),
    ('What are the coding standards?', 'engineering_standards.txt'),
    ('What should a new employee do on their first day?', 'onboarding_guide.txt'),
    ('What are the CloudDesk Pro pricing plans?', 'product_knowledge_base.txt'),
    ('What are the password security requirements?', 'security_policy.txt'),
]
results = []
with httpx.Client(base_url=os.getenv('APP_URL', 'http://127.0.0.1:8000'),
                  headers={'Authorization': 'Bearer ' + os.environ['RAG_API_KEY']}, timeout=180) as client:
    for index, (question, expected) in enumerate(CASES):
        start = time.perf_counter()
        response = client.post('/api/retrieve', json={'question': question})
        response.raise_for_status()
        sources = response.json()['sources']
        rank = next((i + 1 for i, s in enumerate(sources) if s['source'] == expected), 0)
        results.append({'case': index + 1, 'hit_at_5': bool(rank), 'reciprocal_rank': 1/rank if rank else 0,
                        'latency_seconds': round(time.perf_counter() - start, 3)})
summary = {'hit_rate_at_5': statistics.mean(r['hit_at_5'] for r in results),
           'mrr_at_5': statistics.mean(r['reciprocal_rank'] for r in results), 'cases': results}
(ROOT / 'evaluation-results.json').write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
# Optional MLflow: pip install mlflow-skinny. Stores numeric metrics only.
if os.getenv('ENABLE_MLFLOW') == '1':
    import mlflow
    mlflow.set_tracking_uri((ROOT / 'mlruns').as_uri())
    mlflow.set_experiment('local-rag-retrieval')
    with mlflow.start_run():
        mlflow.log_metrics({k: v for k, v in summary.items() if isinstance(v, (float, int))})
        mlflow.log_param('top_k', 5)
