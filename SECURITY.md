# Security and data handling

Do not commit API keys, access tokens, cookies, private keys, holdings, personal profiles, private research, raw browser captures, or delivery-channel identifiers.

Use environment variables for credentials and `*.local.*` or `*.private.*` for local configuration. Those patterns are ignored by Git.

Run this before every push:

```bash
uv run python scripts/public_release_guard.py
```

The guard is a release brake, not a complete secret scanner. Review the staged diff and Git history before publication. If you find a credential in history, revoke it first; deleting the current file is not enough.

Report security problems through GitHub's private vulnerability reporting when available. Do not place sensitive evidence in a public issue.
