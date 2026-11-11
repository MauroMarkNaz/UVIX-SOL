# UVIX-SOL: The Solana Ledger & Cryptographic Anchoring Substrate
## Era IV of the UVIX Architectural Continuum

[![Solana Program](https://img.shields.io/badge/Solana-Anchor%201.2.1-14F195?logo=solana)](https://solana.com)
[![IDL Registry](https://img.shields.io/badge/IDL-wecrypto.app.leaksnipe.idl.win-0052FF)](https://wecryp-unified.leaksnipe.win)
[![Companion Core](https://img.shields.io/badge/Protocol%20Core-UVIX-blueviolet)](https://github.com/MauroMarkNaz/UVIX)
[![PQC Security](https://img.shields.io/badge/Security-Post--Quantum%20(Kyber%2FDilithium)-black)](PQC_SECURITY.md)

---

## 1. Architectural Positioning: The Decoupled Ledger Substrate

In the linear architectural evolution of **UVIX**, blockchain ledger mechanics are strictly decoupled from the core universal protocol:

* **[UVIX (Universal Core)](https://github.com/MauroMarkNaz/UVIX)**: Substrate-agnostic wire protocol (`UVIX-RI-1.0`), dyscalculia-driven topological slug hierarchy (`UVIX.*`), dual local hardware acceleration (RTX 4070 / DirectML NPU), and edge inference mesh (`mistral`, `deepseek`, `qwen`, `llama`).
* **UVIX-SOL (This Repository)**: The dedicated, sovereign Solana execution, verification, and Proof-of-History state anchoring layer.

```
       +-------------------------------------------------------------+
       |                  UVIX UNIVERSAL CORE PROTOCOL               |
       |       Deterministic Wire Codec • Inference • Multi-D1       |
       +-------------------------------------------------------------+
                                      │
                                      ▼ (Cryptographic State Root)
       +-------------------------------------------------------------+
       |               UVIX-SOL ANCHORING & LEDGER LAYER             |
       |  Proof-of-History Clocks • SPL Memo Anchors • Anchor Program |
       +-------------------------------------------------------------+
               │                                      │
               ▼                                      ▼
       [Solana Blockchain]                   [Decentralized Markets]
       • Anchor Program (9HLcTy...)          • Raydium AMM Pools
       • Memo Program (MemoSq...)            • Pump.fun Bonding Curves
       • Slot & Blockhash Authority          • Jupiter Ultra-Fast Routing
```

---

## 2. Linear Historical Genesis

Even though concepts emerged non-linearly across trading execution, decentralized finance experiments, and cryptographic research, the Solana anchoring pipeline sits at the definitive apex of the 4-era arc:

1. **Era I (Topological Invariance)**: Establishing that human intent and system routing rely on stable topological invariants rather than brittle numerical offsets.
2. **Era II (Package & Build Synthesis)**: Standardizing Linux/npm compilation to guarantee byte-for-byte reproducibility across runtimes.
3. **Era III (Deterministic Wire Envelopes)**: Producing self-verifying `UVIX-RI-1.0` envelopes with RFC 8785 Canonical JSON (JCS) and Merkle state hashes.
4. **Era IV (Solana Immutable Commitment — This Substrate)**: Consuming Merkle state roots from Era III and anchoring them into Solana blocks via Proof-of-History timestamps and immutable SPL Memo transactions.

---

## 3. Solana On-Chain Program: `WeCrypto`

* **Program ID**: `9HLcTyxqXTimBXj9RvP2dZtTwZsNdzdiGRNRdUTTUp5B`
* **Canonical IDL**: [`idl/wecrypto.json`](idl/wecrypto.json) and [`solana/wecrypto/app/idl/wecrypto.json`](solana/wecrypto/app/idl/wecrypto.json)
* **Framework**: Anchor `1.2.1` / Agave SDK `v3.1+` / Rust `1.89+`

### Instructions
| Instruction | Accounts | Purpose |
| :--- | :--- | :--- |
| `initialize` | `[payer, config, system_program]` | Initializes the singleton `GlobalConfig` PDA with admin authority and canonical IDL endpoint. |
| `record_turn_proof` | `[payer, config, turn_anchor, system_program]` | Commits a strictly monotonic state turn hash (`[u8; 32]`) anchored to Cloudflare D1 proof turns and Solana slot height. |
| `commit_prediction` | `[payer, config, commitment, system_program]` | Cryptographically commits market probability forecasts (touch/settle basis points) before expiration horizons. |
| `resolve_prediction` | `[authority, config, commitment]` | Records realized market settlement outcomes, settlement price, and quadratic Brier score loss. |
| `log_token_signal` | `[payer, config, signal_record, system_program]` | Stores on-chain forensic assessment (risk score, LP burn/lock status, bundle cluster detection, metadata hash). |
| `update_config` | `[authority, config]` | Administrative pause controls, authority migration, and IDL URI updates. |

### Program Derived Addresses (PDAs)
```rust
// Global configuration singleton
[b"global_config"]

// Proof-of-History turn state commits
[b"poh_turn", sequence.to_le_bytes().as_ref()]

// Horizon prediction commitments
[b"prediction", sequence.to_le_bytes().as_ref()]

// Token security & rugcheck forensics
[b"token_signal", token_mint.as_ref()]
```

---

## 4. The Dual SPL Memo Anchoring Grammar

State roots generated by the UVIX core protocol are written directly to Solana transaction metadata via the SPL Memo Program (`MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr`):

### Codec 1: `uvix-anchor/1` (SHA-256 Merkle Standard)
```
uvix-anchor/1|c=<cluster>|node=<node>|w=<w_start>-<w_end>|i=<from>-<to>|r=<sha256_root>|p=<prev_link>
```

### Codec 2: `uvix-anchor/2` (BLAKE3 Ultra-Fast Merkle Standard)
```
uvix-anchor/2|c=<cluster>|node=<node>|w=<w_start>-<w_end>|i=<from>-<to>|r=<blake3_root>|p=<prev_link>
```

* **Cost**: Exactly 5,000 lamports (base signature fee), zero rent overhead.
* **Proof-of-History Guarantee**: The Solana slot and ledger blockhash serve as the immutable clock authority for state timestamps.

---

## 5. DEX Liquidity & Token Codecs

Located in [`sol_uvix/`](sol_uvix/):
* **`pumpfun.py`**: Bonding curve calculation, virtual SOL/token reserve tracking, and migration trigger monitoring.
* **`raydium.py`**: OpenBook CLOB and CPMM swap instruction encoders with exact slippage math.
* **`transactions.py`**: Versioned Transaction (`v0`) builder with Address Lookup Table (ALT) compression.
* **`tokens.py`**: SPL Token-2022 extension parsing (transfer fees, confidential transfers, metadata pointers).

---

## 6. Directory Layout

```
UVIX-SOL/
├── idl/
│   └── wecrypto.json           # Canonical Anchor IDL
├── solana/
│   └── wecrypto/               # Complete Anchor Rust program suite
│       ├── programs/wecrypto/  # Program source (instructions, state, error, constants)
│       ├── tests/              # LiteSVM automated unit/integration tests
│       ├── Anchor.toml         # Anchor configuration
│       └── Cargo.toml          # Rust workspace manifest
├── sol_uvix/                   # Python client, codecs, DEX builders, transaction compressors
│   ├── bridge.py
│   ├── codec.py
│   ├── pumpfun.py
│   ├── raydium.py
│   ├── tokens.py
│   └── transactions.py
├── pqc.py                      # Post-quantum cryptographic algorithms (Kyber/Dilithium)
├── pqc_api.py                  # PQC verification HTTP endpoints
├── pqc_files.py                # Quantum-resistant file encryption
├── PQC_SECURITY.md             # Security audit & lattice parameters
└── README.md                   # Era IV Architectural Specification
```

---
*Maintained by Mauro Mark Nazareno Fanelli — UVIX Architecture Group*
