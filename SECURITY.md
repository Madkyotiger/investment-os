# Security and data handling

Do not commit API keys, access tokens, cookies, private keys, holdings, personal profiles, private research, raw browser captures, or external endpoint identifiers.

Use environment variables for credentials and `*.local.*` or `*.private.*` for local configuration. Those patterns are ignored by Git.

Investment OS does not store channel credentials or send messages. It writes local research artifacts and a completed manifest with artifact hashes. Any downstream system that distributes an artifact owns destination authorization, credential handling, payload construction, retries, and deduplication outside this repository.

Run this before every push:

```bash
uv run python scripts/public_release_guard.py
```

The guard is a release brake, not a complete secret scanner. Review the staged diff and Git history before publication. If you find a credential in history, revoke it first; deleting the current file is not enough.

Report security problems through GitHub's private vulnerability reporting when available. Do not place sensitive evidence in a public issue.
