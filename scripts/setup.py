"""Generate a local access key without overwriting existing configuration."""
import os
from pathlib import Path
import secrets

root = Path(__file__).resolve().parent.parent
env = root / '.env'
if env.exists():
    print('Existing .env preserved. Open it to find your RAG_API_KEY.')
else:
    content = (root / '.env.example').read_text().replace('GENERATED_BY_SETUP', secrets.token_urlsafe(32))
    # Create owner-readable/writable on POSIX; Windows uses its normal ACLs.
    fd = os.open(env, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as out:
        out.write(content)
    print('Created .env. Open it and copy RAG_API_KEY into the chat settings.')
print('Next: docker compose up -d --build')
