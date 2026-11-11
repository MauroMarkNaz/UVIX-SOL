"""
High-Performance Solana RPC Client with Native UVIX Encapsulation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Queries live Solana RPC clusters and wraps on-chain telemetry into
canonical UVIX-RI-1.0 envelopes.
"""

import os
import json
import requests
from typing import Dict, Any, Optional, List
from .models import SolanaAccountState, SolanaTransactionState
from .codec import encode_uvix_slug

DEFAULT_RPC_ENDPOINTS = [
    os.environ.get("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com"),
    os.environ.get("SOLANA_DEVNET_RPC_URL", "https://api.devnet.solana.com"),
]


class SolanaUVIXClient:
    """Client for querying Solana RPC nodes and emitting UVIX envelopes."""

    def __init__(self, rpc_url: Optional[str] = None, timeout: float = 10.0):
        self.rpc_url = rpc_url or DEFAULT_RPC_ENDPOINTS[0]
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def _rpc_request(self, method: str, params: List[Any]) -> Dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }
        resp = self.session.post(self.rpc_url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"Solana RPC Error: {data['error']}")
        return data.get("result", {})

    def get_slot(self) -> int:
        """Returns current slot."""
        return int(self._rpc_request("getSlot", []))

    def get_balance(self, pubkey: str) -> float:
        """Returns SOL balance for a public key."""
        res = self._rpc_request("getBalance", [pubkey])
        lamports = res.get("value", 0)
        return lamports / 1_000_000_000.0

    def get_account_info(self, pubkey: str) -> Optional[SolanaAccountState]:
        """Queries account info and returns structured SolanaAccountState."""
        res = self._rpc_request("getAccountInfo", [pubkey, {"encoding": "base64"}])
        val = res.get("value")
        if not val:
            return None

        lamports = val.get("lamports", 0)
        data_arr = val.get("data", ["", "base64"])
        b64_str = data_arr[0] if isinstance(data_arr, list) and len(data_arr) > 0 else ""

        return SolanaAccountState(
            pubkey=pubkey,
            lamports=lamports,
            sol_balance=lamports / 1_000_000_000.0,
            owner=val.get("owner", ""),
            executable=val.get("executable", False),
            rent_epoch=val.get("rentEpoch", 0),
            data_base64=b64_str,
            slot=res.get("context", {}).get("slot"),
        )

    def get_account_uvix_slug(self, pubkey: str) -> Optional[str]:
        """Fetches account state and wraps it into a canonical UVIX envelope."""
        acc = self.get_account_info(pubkey)
        if not acc:
            return None

        payload = {
            "protocol": "solana-rpc",
            "type": "account_info",
            "data": acc.to_dict(),
        }
        return encode_uvix_slug(
            payload,
            source_platform="Solana-RPC",
            target_platform="UVIX-Mesh-MultiAgent",
            compatibility_layer="solana-uvix-v1",
        )
