"""
Solana RPC WebSocket Client with Native UVIX Encapsulation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Connects to Solana PubSub WebSocket endpoints (ws:// or wss://),
manages subscriptions (accountSubscribe, logsSubscribe, programSubscribe, slotSubscribe),
and automatically emits canonical UVIX-RI-1.0 envelopes for all notifications.
"""

import json
import time
import threading
from typing import Dict, Any, Optional, Callable, List
from .codec import encode_uvix_slug

DEFAULT_WS_ENDPOINTS = [
    "wss://api.devnet.solana.com",
    "wss://api.mainnet-beta.solana.com",
]


class SolanaUVIXWebSocketClient:
    """Manages WebSocket connections and PubSub streams from Solana RPC nodes."""

    def __init__(self, ws_url: Optional[str] = None, on_slug_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None):
        self.ws_url = ws_url or DEFAULT_WS_ENDPOINTS[0]
        self.on_slug_callback = on_slug_callback
        self.active_subscriptions: Dict[int, Dict[str, Any]] = {}
        self._next_req_id = 1
        self._lock = threading.Lock()

    def create_subscribe_payload(self, method: str, params: Optional[List[Any]] = None) -> Dict[str, Any]:
        """Builds JSON-RPC 2.0 subscription request payload."""
        with self._lock:
            req_id = self._next_req_id
            self._next_req_id += 1

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params or [],
        }

    def create_unsubscribe_payload(self, method: str, subscription_id: int) -> Dict[str, Any]:
        """Builds JSON-RPC 2.0 unsubscription request payload."""
        with self._lock:
            req_id = self._next_req_id
            self._next_req_id += 1

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": [subscription_id],
        }

    # Subscription helpers
    def account_subscribe_payload(self, pubkey: str, commitment: str = "confirmed", encoding: str = "base64") -> Dict[str, Any]:
        return self.create_subscribe_payload("accountSubscribe", [pubkey, {"commitment": commitment, "encoding": encoding}])

    def account_unsubscribe_payload(self, subscription_id: int) -> Dict[str, Any]:
        return self.create_unsubscribe_payload("accountUnsubscribe", subscription_id)

    def program_subscribe_payload(self, program_id: str, commitment: str = "confirmed", encoding: str = "base64") -> Dict[str, Any]:
        return self.create_subscribe_payload("programSubscribe", [program_id, {"commitment": commitment, "encoding": encoding}])

    def program_unsubscribe_payload(self, subscription_id: int) -> Dict[str, Any]:
        return self.create_unsubscribe_payload("programUnsubscribe", subscription_id)

    def logs_subscribe_payload(self, mentions_or_filter: Any = "all", commitment: str = "confirmed") -> Dict[str, Any]:
        return self.create_subscribe_payload("logsSubscribe", [{"mentions": [mentions_or_filter]} if isinstance(mentions_or_filter, str) and mentions_or_filter != "all" else mentions_or_filter, {"commitment": commitment}])

    def logs_unsubscribe_payload(self, subscription_id: int) -> Dict[str, Any]:
        return self.create_unsubscribe_payload("logsUnsubscribe", subscription_id)

    def slot_subscribe_payload(self) -> Dict[str, Any]:
        return self.create_subscribe_payload("slotSubscribe", [])

    def slot_unsubscribe_payload(self, subscription_id: int) -> Dict[str, Any]:
        return self.create_unsubscribe_payload("slotUnsubscribe", subscription_id)

    def block_subscribe_payload(self, commitment: str = "confirmed") -> Dict[str, Any]:
        return self.create_subscribe_payload("blockSubscribe", ["all", {"commitment": commitment}])

    def block_unsubscribe_payload(self, subscription_id: int) -> Dict[str, Any]:
        return self.create_unsubscribe_payload("blockUnsubscribe", subscription_id)

    def process_notification(self, raw_message: str) -> Optional[str]:
        """
        Parses an incoming WebSocket notification message and wraps it into a canonical UVIX slug envelope.
        """
        try:
            msg = json.loads(raw_message)
        except Exception:
            return None

        # Check if message is a notification
        method = msg.get("method")
        params = msg.get("params")
        if not method or not params:
            return None

        sub_id = params.get("subscription")
        result = params.get("result", {})
        context = result.get("context", {}) if isinstance(result, dict) else {}
        slot = context.get("slot")

        uvix_payload = {
            "notification_type": method,
            "subscription_id": sub_id,
            "slot": slot,
            "data": result,
            "received_at": time.time(),
        }

        envelope = encode_uvix_slug(
            uvix_payload,
            source_platform=f"Solana-PubSub-{method}",
            target_platform="UVIX-Mesh-MultiAgent",
            compatibility_layer="solana-ws-uvix-v1",
        )

        if self.on_slug_callback:
            self.on_slug_callback(envelope, uvix_payload)

        return envelope
