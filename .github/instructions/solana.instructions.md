---
applyTo: "solana/wecrypto/**,idl/wecrypto.json"
---

# Solana / Anchor instructions

- Work from `solana/wecrypto/`; the workspace pins Rust 1.89.0 and uses Anchor 1.2.1. The program crate is `programs/wecrypto`.
- Keep instruction handlers in `programs/wecrypto/src/instructions/` and shared account/state definitions, constants, and errors in their corresponding modules. Preserve the program's PDA seeds and checked sequence/state transitions when changing account behavior.
- `anchor build` generates the SBF binary required by the LiteSVM integration tests. Run it before `cargo test --package wecrypto`; use a Cargo test-name filter for a focused test, such as `cargo test --package wecrypto test_initialize`.
- Keep the generated/interface IDL files `idl/wecrypto.json` and `solana/wecrypto/app/idl/wecrypto.json` aligned with changes to the on-chain program interface.
- Run `cargo fmt --check` and `cargo clippy --workspace --all-targets` from the Anchor workspace after Rust changes.
