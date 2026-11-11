---
applyTo: "**/*.py"
---

# Python instructions

- The API entry point is `server.py`; it composes `AIProcessor` with `equity_sim`. `AIProcessor` coordinates `AIRouter`, `LLMGateway`, `EmbeddingEngine`, `HandVectorStore`, and `DossierManager`.
- Routing, model names, provider endpoints, embedding model, and persistence limits are configured in `config/models.json`. External provider credentials are read from the configured environment-variable names; do not put credentials in the JSON file.
- `ai_outputs/`, `dossiers/`, and `vector_store/` are persistent runtime stores. Tests or scripts that touch these defaults should use isolated paths where possible and clean up their own output.
- PQC keypairs default to `Path.home() / ".pqc-keys"`; checked-in material under `security/` is public-key artifact data only. Do not store generated private keys in the repository.
- `pqc.py` selects ML-KEM/ML-DSA when `quantcrypt` is installed and otherwise falls back to X25519/Ed25519. Both modes use AES-GCM for payload encryption. Preserve this distinction in tests and documentation.
- Preserve the relative-import/direct-script fallback in `pqc_api.py` and `pqc_files.py`. Keep module usage examples aligned with the actual public API, including `generate_encryption_keypair()` and `generate_signing_keypair()`.
- The existing `python pqc_files.py test` command uses the default key store and a repository-relative `test_pqc_dir`; account for both paths when invoking it, especially after failures.
