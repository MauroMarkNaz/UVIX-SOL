"""
UVIX Edge Bridge & Multi-Agent Dispatcher
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Dispatches UVIX slugs across Cloudflare Edge routers,
zero-trust neural mesh nodes, and cross-agent telemetry event loops.
"""

import os
import requests
from typing import Dict, Any, Optional, Union
from .codec import encode_uvix_slug, decode_uvix_slug, UVIXSlug
from .models import AgentHandoffPayload

DEFAULT_GATEWAY_URL = os.environ.get("UVIX_GATEWAY_URL", "https://edge.uvix-sol.network/uvix")


class UVIXEdgeBridge:
    """Bridge for broadcasting and receiving UVIX envelopes across mesh endpoints."""

    def __init__(self, gateway_url: Optional[str] = None, timeout: float = 8.0):
        self.gateway_url = gateway_url or DEFAULT_GATEWAY_URL
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "SOL-UVIX-Bridge/1.0",
        })

    def dispatch_slug(self, envelope: str, destination_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Dispatches a raw UVIX envelope string to the edge gateway.
        """
        target = destination_url or self.gateway_url
        payload = {"envelope": envelope}
        resp = self.session.post(target, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def dispatch_telemetry(self,
                           payload: Dict[str, Any],
                           source_platform: str = "Solana-Feeder",
                           target_platform: str = "UVIX-Mesh-MultiAgent",
                           compatibility_layer: str = "solana-uvix-v1",
                           destination_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Encodes telemetry payload into a canonical UVIX slug envelope and dispatches to edge router.
        """
        envelope = encode_uvix_slug(
            payload,
            source_platform=source_platform,
            target_platform=target_platform,
            compatibility_layer=compatibility_layer,
        )
        return self.dispatch_slug(envelope, destination_url=destination_url)

    def dispatch_handoff(self,
                         source_agent: str,
                         target_agent: str,
                         intent: str,
                         action_type: str,
                         context: Dict[str, Any],
                         solana_data: Optional[Dict[str, Any]] = None,
                         destination_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Encapsulates an agent handoff payload into a UVIX envelope and dispatches it.
        """
        handoff = AgentHandoffPayload(
            source_agent=source_agent,
            target_agent=target_agent,
            intent=intent,
            action_type=action_type,
            context=context,
            solana_data=solana_data,
        )
        envelope = encode_uvix_slug(
            handoff.to_dict(),
            source_platform=f"agent-{source_agent}",
            target_platform=f"agent-{target_agent}",
            compatibility_layer="solana-agent-handoff-v1",
        )
        return self.dispatch_slug(envelope, destination_url=destination_url)

    @staticmethod
    def format_discord_embed(slug_or_envelope: Union[str, UVIXSlug, Dict[str, Any]],
                             title: Optional[str] = None) -> Dict[str, Any]:
        """
        Constructs a structured Discord embed payload for mesh bot integrations.
        """
        if isinstance(slug_or_envelope, str):
            slug = decode_uvix_slug(slug_or_envelope)
        elif isinstance(slug_or_envelope, UVIXSlug):
            slug = slug_or_envelope
        elif isinstance(slug_or_envelope, dict) and "payload_hash" in slug_or_envelope:
            slug = UVIXSlug(**slug_or_envelope)
        else:
            raise ValueError(f"Cannot format embed from object of type {type(slug_or_envelope)}")

        raw_preview = str(slug.raw_payload)
        if len(raw_preview) > 500:
            raw_preview = raw_preview[:497] + "..."

        embed = {
            "title": title or f"📡 SOL-UVIX Telemetry | {slug.raw_payload.get('protocol', 'UVIX-RI-1.0')}",
            "color": 0x14F195,  # Solana green
            "fields": [
                {"name": "Source", "value": f"`{slug.source_platform}`", "inline": True},
                {"name": "Target", "value": f"`{slug.target_platform}`", "inline": True},
                {"name": "Protocol", "value": f"`{slug.compatibility_layer}`", "inline": True},
                {"name": "Payload Hash (SHA-256)", "value": f"`{slug.payload_hash[:16]}...`", "inline": False},
                {"name": "Payload Preview", "value": f"```{raw_preview}```", "inline": False},
            ],
            "footer": {
                "text": "SOL-UVIX Bridge • Neural Mesh Telemetry",
            },
        }
        return embed

    # Backward-compatible alias
    format_leaksnipe_discord_embed = format_discord_embed

    def stream_to_discord(self,
                          webhook_url: str,
                          envelope: str,
                          title: Optional[str] = None) -> Dict[str, Any]:
        """
        Streams a UVIX envelope to a Discord webhook with formatted telemetry.
        """
        embed = self.format_discord_embed(envelope, title=title)
        payload = {
            "content": f"**UVIX Envelope Received:**\n```\n{envelope[:120]}...\n```",
            "embeds": [embed],
        }
        resp = self.session.post(webhook_url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return {"status": "dispatched", "status_code": resp.status_code}
