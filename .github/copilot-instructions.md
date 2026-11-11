# AI Poker Coach - Workspace Instructions

## Project Overview
This repository combines a Python poker-analysis API and PQC utilities with a separate Solana Anchor program for WeCrypto on-chain state and prediction verification. The Python and Solana projects have separate build and test workflows.

## Core Technologies
- **Languages**: Python 3.10+ (Docker image uses 3.11) and Rust 1.89.0
- **API**: FastAPI / Uvicorn
- **Solana**: Anchor 1.2.1, with LiteSVM tests
- **Cryptography**: 
  - `quantcrypt` (NIST PQC: ML-KEM, ML-DSA)
  - `cryptography` (Hybrid encryption: AES-GCM, HKDF)
- **Key Standards**: 
  - Key Encapsulation: ML-KEM-1024, ML-KEM-768, ML-KEM-512
  - Digital Signatures: ML-DSA-87, ML-DSA-65, ML-DSA-44

## Architecture and Patterns
- **Python API and analysis**:
  - `server.py` exposes the FastAPI bridge and delegates hand analysis to `AIProcessor`; it also calls `equity_sim` for equity calculations.
  - `ai_processor.py` coordinates routing, model inference, embeddings, similarity search, output persistence, and dossier updates. `ai_router.py` reads routing and model settings from `config/models.json`.
  - `poker_engine.py`, `equity_sim.py`, and `nash_train.py` contain card evaluation, Monte Carlo equity, and CFR training logic.
- **PQC modules**:
  - `pqc.py` owns cryptographic primitives and `PQCKeyStore`; `pqc_api.py` provides API-client mixins; `pqc_files.py` provides file and backup encryption services.
- **Solana program**: `solana/wecrypto/programs/wecrypto/` contains the Anchor program, split into instruction handlers and shared state/constants/errors. The program IDL is kept in both `idl/wecrypto.json` and `solana/wecrypto/app/idl/wecrypto.json`; keep them synchronized when changing the program interface.
- **Runtime data**: AI results, dossiers, and vector indexes are persisted under `ai_outputs/`, `dossiers/`, and `vector_store/` by default. These are runtime data locations, not source modules.
- **Import Strategy**: PQC modules use `try-except ImportError` blocks to support both package imports and direct script execution (e.g., `from .pqc import ...` vs `from pqc import ...`). Preserve these guards.
- **Key Management**:
  - Runtime keys stored in `~/.pqc-keys` (handled by `PQCKeyStore`).
  - `security/` contains repository-provided public-key artifacts; generated keypairs belong in the runtime key store.

## Coding Conventions
- **Type Hinting**: Use strict type hints (`typing` module) for all function arguments and return values.
- **Docstrings**: 
  - Module-level docstrings must include a "Usage" section with copy-pasteable examples.
  - Class and method docstrings should clearly describe behavior, arguments, and return values.
  - See `pqc.py` or `pqc_files.py` for the standard docstring format.
- **Error Handling**: Use specific exceptions (`ValueError`, `ImportError`) over generic ones.

## Security Guidelines
- **NIST Compliance**: Always prioritize FIPS 203/204 algorithms (ML-KEM, ML-DSA).
- **Hybrid Encryption**: Use PQC for key exchange/encapsulation, but rely on standard AES-GCM for symmetric data encryption (as implemented in `pqc.py` logic).
- **Cleanup**: Ensure sensitive key material (especially private keys) is handled securely and temporary files are cleaned up (see `REVIEW_TASKS.md` regarding `pqc_files.py`).

## Common Tasks (Ref: REVIEW_TASKS.md)
- Check each item against current code; `REVIEW_TASKS.md` may include items already resolved.
- `pqc.py` exposes `generate_encryption_keypair()` and `generate_signing_keypair()`; its module usage example still calls the nonexistent `generate_keypair()`.
- Maintain documentation alignment with implementation (especially key storage paths).

## Build and Test
- Install the Python API dependencies from the repository root with `pip install -r requirements.txt`.
- Run the API locally with `python server.py` (binds to `127.0.0.1:8000`).
- The file-service self-test is `python pqc_files.py test`. It writes a key named `test-file-key` to the default `~/.pqc-keys` store and creates `test_pqc_dir` in the current directory; isolate or clean up those artifacts when running it. It is not a single-test framework.
- The PQC GitHub Actions workflow currently invokes `python pqc.py test`, but `pqc.py` does not implement that CLI subcommand. Do not treat that workflow command as a passing verification until it is reconciled with the CLI.
- For the Anchor program, run from `solana/wecrypto/`:
  - `anchor build`
  - `cargo test --package wecrypto`
  - Focus a Rust test by name, e.g. `cargo test --package wecrypto test_initialize`
  - `cargo fmt --check` and `cargo clippy --workspace --all-targets`
- The LiteSVM test embeds `target/deploy/wecrypto.so`; run `anchor build` before the Rust tests.

## Anti-Patterns
- **Hardcoding Paths**: Avoid hardcoding paths outside of default constants. Use `pathlib.Path`.
- **Ignoring Imports**: Do not remove the `try-except` import guard; it is essential for the module's dual usage.
- **PQC fallback assumptions**: When `quantcrypt` is unavailable, `pqc.py` uses X25519/Ed25519 with AES-GCM. Keep the active algorithm mode explicit when changing or documenting cryptographic behavior.
