"""
Raydium AMM Protocol Decoder & Swap Simulation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Parses on-chain binary account state for Raydium V4 Liquidity Pools,
calculates swap reserves, pricing, simulates constant-product swaps,
and generates UVIX slugs.
"""

from typing import Dict, Any, Optional
from .models import RaydiumPoolState
from .codec import encode_uvix_slug

RAYDIUM_V4_PROGRAM_ID = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"


class RaydiumDecoder:
    """Analytical engine and decoder for Raydium liquidity pools."""

    @staticmethod
    def calculate_pool_state(pool_id: str,
                             base_mint: str,
                             quote_mint: str,
                             base_vault: str,
                             quote_vault: str,
                             base_reserve: int,
                             quote_reserve: int,
                             base_decimals: int = 9,
                             quote_decimals: int = 6,
                             lp_supply: int = 0) -> RaydiumPoolState:
        """
        Calculates price and constructs RaydiumPoolState.
        Price = (quote_reserve / 10^quote_decimals) / (base_reserve / 10^base_decimals)
        """
        if base_reserve > 0:
            norm_base = base_reserve / (10 ** base_decimals)
            norm_quote = quote_reserve / (10 ** quote_decimals)
            price = norm_quote / norm_base if norm_base > 0 else 0.0
        else:
            price = 0.0

        return RaydiumPoolState(
            pool_id=pool_id,
            base_mint=base_mint,
            quote_mint=quote_mint,
            base_vault=base_vault,
            quote_vault=quote_vault,
            base_reserve=base_reserve,
            quote_reserve=quote_reserve,
            price=price,
            lp_supply=lp_supply,
        )

    @staticmethod
    def simulate_swap(state: RaydiumPoolState,
                      amount_in: int,
                      is_base_to_quote: bool,
                      fee_bps: int = 25,
                      base_decimals: int = 9,
                      quote_decimals: int = 6) -> Dict[str, Any]:
        """
        Simulates constant-product swap on Raydium AMM V4 pool.
        k = base_reserve * quote_reserve
        fee: fee_bps (standard Raydium V4 fee = 25 bps / 0.25%)
        """
        if amount_in <= 0:
            raise ValueError("amount_in must be greater than zero")

        if is_base_to_quote:
            res_in = state.base_reserve
            res_out = state.quote_reserve
            dec_in = base_decimals
            dec_out = quote_decimals
        else:
            res_in = state.quote_reserve
            res_out = state.base_reserve
            dec_in = quote_decimals
            dec_out = base_decimals

        if res_in <= 0 or res_out <= 0:
            raise ValueError("Insufficient pool liquidity for swap")

        fee_amount = (amount_in * fee_bps) // 10_000
        in_after_fee = amount_in - fee_amount

        numerator = in_after_fee * res_out
        denominator = res_in + in_after_fee
        amount_out = numerator // denominator

        new_res_in = res_in + amount_in
        new_res_out = res_out - amount_out

        # Execution price = (amount_quote / 10^quote_dec) / (amount_base / 10^base_dec)
        if is_base_to_quote:
            norm_base = amount_in / (10 ** base_decimals)
            norm_quote = amount_out / (10 ** quote_decimals)
            exec_price = norm_quote / norm_base if norm_base > 0 else 0.0
            price_impact = ((state.price - exec_price) / state.price) * 100.0 if state.price > 0 else 0.0
            new_base_res = new_res_in
            new_quote_res = new_res_out
        else:
            norm_quote = amount_in / (10 ** quote_decimals)
            norm_base = amount_out / (10 ** base_decimals)
            exec_price = norm_quote / norm_base if norm_base > 0 else 0.0
            price_impact = ((exec_price - state.price) / state.price) * 100.0 if state.price > 0 else 0.0
            new_quote_res = new_res_in
            new_base_res = new_res_out

        return {
            "amount_in": amount_in,
            "fee_amount": fee_amount,
            "net_amount_in": in_after_fee,
            "amount_out": amount_out,
            "is_base_to_quote": is_base_to_quote,
            "new_base_reserve": new_base_res,
            "new_quote_reserve": new_quote_res,
            "execution_price": exec_price,
            "pool_price_before": state.price,
            "price_impact_pct": round(price_impact, 4),
        }

    @classmethod
    def to_uvix_slug(cls, state: RaydiumPoolState) -> str:
        """Wraps Raydium pool telemetry into a standard UVIX envelope."""
        payload = {
            "protocol": "raydium-amm-v4",
            "type": "pool_reserves_telemetry",
            "data": state.to_dict(),
        }
        return encode_uvix_slug(
            payload,
            source_platform="Raydium-Telemetry",
            target_platform="UVIX-Mesh-MultiAgent",
            compatibility_layer="solana-raydium-uvix",
        )
