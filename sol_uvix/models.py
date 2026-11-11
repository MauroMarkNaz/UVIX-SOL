"""
Data Models for Solana & UVIX Interoperability
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Defines typed schemas for Solana RPC telemetry, bonding curves,
liquidity pool metrics, and multi-agent coordination envelopes.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
import time


@dataclass
class SolanaAccountState:
    pubkey: str
    lamports: int
    sol_balance: float
    owner: str
    executable: bool
    rent_epoch: int
    data_base64: Optional[str] = None
    slot: Optional[int] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PumpFunBondingCurveState:
    mint: str
    bonding_curve: str
    associated_bonding_curve: str
    virtual_token_reserves: int
    virtual_sol_reserves: int
    real_token_reserves: int
    real_sol_reserves: int
    token_total_supply: int
    complete: bool
    price_in_sol: float
    market_cap_sol: float
    progress_percent: float
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RaydiumPoolState:
    pool_id: str
    base_mint: str
    quote_mint: str
    base_vault: str
    quote_vault: str
    base_reserve: int
    quote_reserve: int
    price: float
    lp_supply: int
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SolanaTransactionState:
    signature: str
    slot: int
    err: Optional[Any]
    fee_lamports: int
    compute_units_consumed: Optional[int]
    signers: List[str]
    recent_blockhash: str
    log_messages: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AgentHandoffPayload:
    source_agent: str
    target_agent: str
    intent: str
    action_type: str
    context: Dict[str, Any]
    solana_data: Optional[Dict[str, Any]] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
