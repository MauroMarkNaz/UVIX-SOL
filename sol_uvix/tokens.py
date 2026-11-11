"""
SPL Token & Token-2022 Parser and UVIX Encapsulation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Parses on-chain binary account state for:
- Standard SPL Token Mints (82 bytes) & Token Accounts (165 bytes)
- Token-2022 (Token Extensions Program) Type-Length-Value (TLV) regions
- TransferFeeConfig (mint) and TransferFeeAmount (account) extensions
- Fee calculation math (basis points fee with epoch cutoffs and caps)
- InterestBearingConfig (mint) and interest accrual math
- TokenMetadata (mint) on-chain names, symbols, URIs, and key-values
- MetadataPointer extensions
- Deterministic UVIX slug encapsulation (UVIX-RI-1.0)
"""

import struct
import base64
import time
import math
from enum import IntEnum
from typing import Dict, Any, Optional, List, Tuple, Union
from dataclasses import dataclass, field, asdict

from .codec import encode_uvix_slug
from .transactions import b58encode, b58decode

# Well-Known SPL Program IDs
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022_PROGRAM_ID = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
ASSOCIATED_TOKEN_PROGRAM_ID = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"

# Base Layout Lengths
MINT_LAYOUT_SIZE = 82
TOKEN_ACCOUNT_LAYOUT_SIZE = 165


class ExtensionType(IntEnum):
    """Token-2022 Extension Discriminators."""
    Uninitialized = 0
    TransferFeeConfig = 1
    TransferFeeAmount = 2
    MintCloseAuthority = 3
    ConfidentialTransferMint = 4
    ConfidentialTransferAccount = 5
    DefaultAccountState = 6
    ImmutableOwner = 7
    MemoTransfer = 8
    NonTransferable = 9
    InterestBearingConfig = 10
    CpiGuard = 11
    PermanentDelegate = 12
    NonTransferableAccount = 13
    TransferHook = 14
    TransferHookAccount = 15
    MetadataPointer = 18
    TokenMetadata = 19
    GroupPointer = 20
    TokenGroup = 21
    GroupMemberPointer = 22
    TokenGroupMember = 23


@dataclass
class TransferFee:
    """Epoch-specific fee parameters for TransferFeeConfig."""
    epoch: int
    transfer_fee_basis_points: int  # in bps, e.g. 150 = 1.5%
    maximum_fee: int  # in raw token units

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TransferFeeConfig:
    """Transfer fee configuration extension for Token-2022 mint accounts."""
    transfer_fee_config_authority: Optional[str]
    withdraw_withheld_authority: Optional[str]
    withheld_amount: int
    older_transfer_fee: TransferFee
    newer_transfer_fee: TransferFee

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transfer_fee_config_authority": self.transfer_fee_config_authority,
            "withdraw_withheld_authority": self.withdraw_withheld_authority,
            "withheld_amount": self.withheld_amount,
            "older_transfer_fee": self.older_transfer_fee.to_dict(),
            "newer_transfer_fee": self.newer_transfer_fee.to_dict(),
        }

    def calculate_fee(self, amount: int, current_epoch: Optional[int] = None) -> int:
        """
        Calculates transfer fee in token units.
        If current_epoch is specified and current_epoch < newer_transfer_fee.epoch,
        the older_transfer_fee rule applies; otherwise newer_transfer_fee applies.
        Uses Solana's standard div_ceil formula:
        fee = ceil(amount * fee_basis_points / 10,000)
        capped at maximum_fee.
        """
        if amount <= 0:
            return 0

        fee_rule = self.newer_transfer_fee
        if current_epoch is not None and current_epoch < self.newer_transfer_fee.epoch:
            fee_rule = self.older_transfer_fee

        if fee_rule.transfer_fee_basis_points == 0:
            return 0

        # Exact integer div_ceil: (amount * fee_bps + 9999) // 10000
        raw_fee = (amount * fee_rule.transfer_fee_basis_points + 9999) // 10_000
        return min(raw_fee, fee_rule.maximum_fee)


@dataclass
class InterestBearingConfig:
    """Interest-bearing configuration extension for Token-2022 mint accounts."""
    rate_authority: str
    initialization_timestamp: int
    pre_update_average_rate: int  # in bps
    last_update_timestamp: int
    current_rate: int  # in bps, e.g. 500 = 5.0%

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def calculate_accrued_amount(self, principal: int, current_timestamp: Optional[int] = None) -> float:
        """Calculates compounded or simple accrued amount based on current_rate."""
        ts = current_timestamp if current_timestamp is not None else int(time.time())
        elapsed_seconds = max(0, ts - self.last_update_timestamp)
        elapsed_years = elapsed_seconds / 31_536_000.0  # 365 days
        rate_decimal = self.current_rate / 10_000.0
        # Continuous compounding approximation: principal * exp(rate * time)
        return principal * math.exp(rate_decimal * elapsed_years)


@dataclass
class TokenMetadata:
    """On-chain Token-2022 metadata extension."""
    update_authority: Optional[str]
    mint: str
    name: str
    symbol: str
    uri: str
    additional_metadata: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MetadataPointer:
    """MetadataPointer extension pointing to on-chain metadata account."""
    authority: Optional[str]
    metadata_address: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SPLTokenMint:
    """Decoded state of an SPL Token or Token-2022 Mint account."""
    mint: str
    mint_authority: Optional[str]
    supply: int
    decimals: int
    is_initialized: bool
    freeze_authority: Optional[str]
    ui_supply: float
    is_token_2022: bool = False
    transfer_fee_config: Optional[TransferFeeConfig] = None
    interest_bearing_config: Optional[InterestBearingConfig] = None
    metadata: Optional[TokenMetadata] = None
    metadata_pointer: Optional[MetadataPointer] = None
    extensions: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mint": self.mint,
            "mint_authority": self.mint_authority,
            "supply": self.supply,
            "decimals": self.decimals,
            "is_initialized": self.is_initialized,
            "freeze_authority": self.freeze_authority,
            "ui_supply": self.ui_supply,
            "is_token_2022": self.is_token_2022,
            "transfer_fee_config": self.transfer_fee_config.to_dict() if self.transfer_fee_config else None,
            "interest_bearing_config": self.interest_bearing_config.to_dict() if self.interest_bearing_config else None,
            "metadata": self.metadata.to_dict() if self.metadata else None,
            "metadata_pointer": self.metadata_pointer.to_dict() if self.metadata_pointer else None,
            "extensions": self.extensions,
            "timestamp": self.timestamp,
        }

    def calculate_transfer_fee(self, amount: int, current_epoch: Optional[int] = None) -> int:
        """Calculates transfer fee for a given amount in raw token units."""
        if not self.transfer_fee_config:
            return 0
        return self.transfer_fee_config.calculate_fee(amount, current_epoch)

    def to_uvix_slug(self) -> str:
        payload = {
            "protocol": "spl-token-2022" if self.is_token_2022 else "spl-token",
            "type": "mint_state",
            "data": self.to_dict(),
        }
        return encode_uvix_slug(
            payload,
            source_platform="Solana-TokenEngine",
            target_platform="UVIX-Mesh-MultiAgent",
            compatibility_layer="solana-token-uvix-v1",
        )


@dataclass
class SPLTokenAccount:
    """Decoded state of an SPL Token or Token-2022 Token (Holding) account."""
    pubkey: str
    mint: str
    owner: str
    amount: int
    ui_amount: Optional[float]
    delegate: Optional[str]
    state: str  # "uninitialized", "initialized", "frozen"
    is_native: bool
    native_rent_lamports: Optional[int]
    delegated_amount: int
    close_authority: Optional[str]
    is_token_2022: bool = False
    transfer_fee_amount: Optional[int] = None  # Withheld tokens waiting to be harvested
    extensions: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pubkey": self.pubkey,
            "mint": self.mint,
            "owner": self.owner,
            "amount": self.amount,
            "ui_amount": self.ui_amount,
            "delegate": self.delegate,
            "state": self.state,
            "is_native": self.is_native,
            "native_rent_lamports": self.native_rent_lamports,
            "delegated_amount": self.delegated_amount,
            "close_authority": self.close_authority,
            "is_token_2022": self.is_token_2022,
            "transfer_fee_amount": self.transfer_fee_amount,
            "extensions": self.extensions,
            "timestamp": self.timestamp,
        }

    def to_uvix_slug(self) -> str:
        payload = {
            "protocol": "spl-token-2022" if self.is_token_2022 else "spl-token",
            "type": "token_account_state",
            "data": self.to_dict(),
        }
        return encode_uvix_slug(
            payload,
            source_platform="Solana-TokenEngine",
            target_platform="UVIX-Mesh-MultiAgent",
            compatibility_layer="solana-token-uvix-v1",
        )


def _unpack_coption_pubkey(data: bytes, offset: int) -> Tuple[Optional[str], int]:
    """Unpacks a 36-byte COption<Pubkey> (4-byte tag + 32-byte pubkey)."""
    tag = struct.unpack_from("<I", data, offset)[0]
    offset += 4
    if tag == 1:
        key_bytes = data[offset : offset + 32]
        return b58encode(key_bytes), offset + 32
    else:
        return None, offset + 32


def _pack_coption_pubkey(key: Optional[str]) -> bytes:
    """Packs an Optional[str] base58 pubkey into 36-byte COption<Pubkey>."""
    if key:
        return struct.pack("<I32s", 1, b58decode(key))
    else:
        return struct.pack("<I32s", 0, b"\x00" * 32)


def _unpack_borsh_string(data: bytes, offset: int) -> Tuple[str, int]:
    """Unpacks a 4-byte length prefixed UTF-8 string."""
    str_len = struct.unpack_from("<I", data, offset)[0]
    offset += 4
    if offset + str_len > len(data):
        raise ValueError("Buffer underflow reading string")
    s = data[offset : offset + str_len].decode("utf-8")
    return s, offset + str_len


def _pack_borsh_string(s: str) -> bytes:
    """Packs a UTF-8 string with a 4-byte little-endian length prefix."""
    raw = s.encode("utf-8")
    return struct.pack("<I", len(raw)) + raw


def _parse_tlv_extensions(data: bytes, start_offset: int) -> Dict[str, Any]:
    """
    Parses Type-Length-Value (TLV) extension blocks starting at start_offset.
    """
    extensions: Dict[str, Any] = {}
    offset = start_offset

    while offset + 4 <= len(data):
        ext_type = struct.unpack_from("<H", data, offset)[0]
        ext_len = struct.unpack_from("<H", data, offset + 2)[0]
        offset += 4

        if offset + ext_len > len(data):
            break

        val_bytes = data[offset : offset + ext_len]
        offset += ext_len

        if ext_type == ExtensionType.TransferFeeConfig:
            if ext_len >= 128:
                auth, off = _unpack_coption_pubkey(val_bytes, 0)
                withdraw_auth, off = _unpack_coption_pubkey(val_bytes, off)
                withheld = struct.unpack_from("<Q", val_bytes, off)[0]
                off += 8

                # Older transfer fee (24 bytes)
                old_epoch, old_bps, _, old_max = struct.unpack_from("<QH6sQ", val_bytes, off)
                off += 24

                # Newer transfer fee (24 bytes)
                new_epoch, new_bps, _, new_max = struct.unpack_from("<QH6sQ", val_bytes, off)

                extensions["transfer_fee_config"] = TransferFeeConfig(
                    transfer_fee_config_authority=auth,
                    withdraw_withheld_authority=withdraw_auth,
                    withheld_amount=withheld,
                    older_transfer_fee=TransferFee(old_epoch, old_bps, old_max),
                    newer_transfer_fee=TransferFee(new_epoch, new_bps, new_max),
                )

        elif ext_type == ExtensionType.TransferFeeAmount:
            if ext_len >= 8:
                withheld_amount = struct.unpack_from("<Q", val_bytes, 0)[0]
                extensions["transfer_fee_amount"] = withheld_amount

        elif ext_type == ExtensionType.InterestBearingConfig:
            if ext_len >= 52:
                rate_auth_bytes = val_bytes[:32]
                init_ts, pre_rate, last_ts, curr_rate = struct.unpack_from("<qhqh", val_bytes, 32)
                extensions["interest_bearing_config"] = InterestBearingConfig(
                    rate_authority=b58encode(rate_auth_bytes),
                    initialization_timestamp=init_ts,
                    pre_update_average_rate=pre_rate,
                    last_update_timestamp=last_ts,
                    current_rate=curr_rate,
                )

        elif ext_type == ExtensionType.MetadataPointer:
            if ext_len >= 72:
                auth, off = _unpack_coption_pubkey(val_bytes, 0)
                meta_addr, _ = _unpack_coption_pubkey(val_bytes, off)
                extensions["metadata_pointer"] = MetadataPointer(
                    authority=auth,
                    metadata_address=meta_addr,
                )

        elif ext_type == ExtensionType.TokenMetadata:
            try:
                auth, off = _unpack_coption_pubkey(val_bytes, 0)
                mint_bytes = val_bytes[off : off + 32]
                mint_str = b58encode(mint_bytes)
                off += 32
                name, off = _unpack_borsh_string(val_bytes, off)
                symbol, off = _unpack_borsh_string(val_bytes, off)
                uri, off = _unpack_borsh_string(val_bytes, off)

                additional_meta = {}
                if off + 4 <= len(val_bytes):
                    num_additional = struct.unpack_from("<I", val_bytes, off)[0]
                    off += 4
                    for _ in range(num_additional):
                        k, off = _unpack_borsh_string(val_bytes, off)
                        v, off = _unpack_borsh_string(val_bytes, off)
                        additional_meta[k] = v

                extensions["metadata"] = TokenMetadata(
                    update_authority=auth,
                    mint=mint_str,
                    name=name,
                    symbol=symbol,
                    uri=uri,
                    additional_metadata=additional_meta,
                )
            except Exception:
                pass

        elif ext_type == ExtensionType.ImmutableOwner:
            extensions["immutable_owner"] = True

        elif ext_type == ExtensionType.DefaultAccountState:
            if ext_len >= 1:
                extensions["default_account_state"] = val_bytes[0]

        elif ext_type == ExtensionType.MemoTransfer:
            if ext_len >= 1:
                extensions["require_memo_transfer"] = bool(val_bytes[0])

        elif ext_type == ExtensionType.CpiGuard:
            if ext_len >= 1:
                extensions["cpi_guard"] = bool(val_bytes[0])

        else:
            extensions[f"extension_{ext_type}"] = val_bytes.hex()

    return extensions


class SPLTokenDecoder:
    """Analytical engine and parser for standard SPL Tokens and Token-2022."""

    @staticmethod
    def decode_mint_data(raw_bytes: bytes, mint_pubkey: str = "") -> SPLTokenMint:
        """
        Parses raw on-chain bytes for an SPL Token or Token-2022 Mint account.
        """
        if len(raw_bytes) < MINT_LAYOUT_SIZE:
            raise ValueError(f"Byte length {len(raw_bytes)} is shorter than SPL mint size {MINT_LAYOUT_SIZE}")

        mint_auth, off = _unpack_coption_pubkey(raw_bytes, 0)
        supply, decimals, is_initialized = struct.unpack_from("<QBB", raw_bytes, off)
        off += 10
        freeze_auth, off = _unpack_coption_pubkey(raw_bytes, off)

        ui_supply = supply / (10 ** decimals) if decimals > 0 else float(supply)
        is_token_2022 = len(raw_bytes) > MINT_LAYOUT_SIZE

        transfer_fee_cfg = None
        interest_cfg = None
        metadata = None
        metadata_pointer = None
        extensions = {}

        if is_token_2022:
            # Token-2022 mint accounts:
            # Often padded to 165 bytes with byte 165 = 1 (AccountType::Mint), then TLV at 166.
            # Or TLV starts at byte 82 if unpadded.
            tlv_start = MINT_LAYOUT_SIZE
            if len(raw_bytes) >= 166 and raw_bytes[165] == 1:
                tlv_start = 166
            elif len(raw_bytes) >= 165:
                tlv_start = 165

            parsed_exts = _parse_tlv_extensions(raw_bytes, tlv_start)
            # If nothing found and tlv_start was 165/166, attempt from byte 82
            if not parsed_exts and tlv_start != MINT_LAYOUT_SIZE:
                parsed_exts = _parse_tlv_extensions(raw_bytes, MINT_LAYOUT_SIZE)

            transfer_fee_cfg = parsed_exts.pop("transfer_fee_config", None)
            interest_cfg = parsed_exts.pop("interest_bearing_config", None)
            metadata = parsed_exts.pop("metadata", None)
            metadata_pointer = parsed_exts.pop("metadata_pointer", None)
            extensions = parsed_exts

        return SPLTokenMint(
            mint=mint_pubkey,
            mint_authority=mint_auth,
            supply=supply,
            decimals=decimals,
            is_initialized=bool(is_initialized),
            freeze_authority=freeze_auth,
            ui_supply=ui_supply,
            is_token_2022=is_token_2022,
            transfer_fee_config=transfer_fee_cfg,
            interest_bearing_config=interest_cfg,
            metadata=metadata,
            metadata_pointer=metadata_pointer,
            extensions=extensions,
        )

    @classmethod
    def decode_mint_base64(cls, b64_str: str, mint_pubkey: str = "") -> SPLTokenMint:
        """Parses mint state from Base64 string directly from RPC."""
        return cls.decode_mint_data(base64.b64decode(b64_str), mint_pubkey=mint_pubkey)

    @staticmethod
    def decode_token_account_data(raw_bytes: bytes, account_pubkey: str = "") -> SPLTokenAccount:
        """
        Parses raw on-chain bytes for an SPL Token or Token-2022 Token account (165 bytes).
        """
        if len(raw_bytes) < TOKEN_ACCOUNT_LAYOUT_SIZE:
            raise ValueError(f"Byte length {len(raw_bytes)} is shorter than SPL token account size {TOKEN_ACCOUNT_LAYOUT_SIZE}")

        mint_bytes = raw_bytes[0:32]
        mint_str = b58encode(mint_bytes)
        owner_bytes = raw_bytes[32:64]
        owner_str = b58encode(owner_bytes)

        amount = struct.unpack_from("<Q", raw_bytes, 64)[0]
        off = 72

        delegate, off = _unpack_coption_pubkey(raw_bytes, off)
        state_byte = raw_bytes[off]
        off += 1

        state_map = {0: "uninitialized", 1: "initialized", 2: "frozen"}
        state_str = state_map.get(state_byte, "unknown")

        # is_native: COption<u64> (4 bytes tag + 8 bytes lamports)
        is_native_tag = struct.unpack_from("<I", raw_bytes, off)[0]
        off += 4
        if is_native_tag == 1:
            is_native = True
            native_rent = struct.unpack_from("<Q", raw_bytes, off)[0]
        else:
            is_native = False
            native_rent = None
        off += 8

        delegated_amount = struct.unpack_from("<Q", raw_bytes, off)[0]
        off += 8

        close_auth, off = _unpack_coption_pubkey(raw_bytes, off)

        is_token_2022 = len(raw_bytes) > TOKEN_ACCOUNT_LAYOUT_SIZE
        transfer_fee_amount = None
        extensions = {}

        if is_token_2022:
            # TLV start in token account: byte 166 if AccountType byte (2) is at 165, or 165
            tlv_start = TOKEN_ACCOUNT_LAYOUT_SIZE
            if len(raw_bytes) > 165 and raw_bytes[165] == 2:
                tlv_start = 166

            parsed_exts = _parse_tlv_extensions(raw_bytes, tlv_start)
            if not parsed_exts and tlv_start != TOKEN_ACCOUNT_LAYOUT_SIZE:
                parsed_exts = _parse_tlv_extensions(raw_bytes, TOKEN_ACCOUNT_LAYOUT_SIZE)

            transfer_fee_amount = parsed_exts.pop("transfer_fee_amount", None)
            extensions = parsed_exts

        return SPLTokenAccount(
            pubkey=account_pubkey,
            mint=mint_str,
            owner=owner_str,
            amount=amount,
            ui_amount=None,  # Decimals required to compute ui_amount
            delegate=delegate,
            state=state_str,
            is_native=is_native,
            native_rent_lamports=native_rent,
            delegated_amount=delegated_amount,
            close_authority=close_auth,
            is_token_2022=is_token_2022,
            transfer_fee_amount=transfer_fee_amount,
            extensions=extensions,
        )

    @classmethod
    def decode_token_account_base64(cls, b64_str: str, account_pubkey: str = "") -> SPLTokenAccount:
        """Parses token account state from Base64 string directly from RPC."""
        return cls.decode_token_account_data(base64.b64decode(b64_str), account_pubkey=account_pubkey)

    @staticmethod
    def encode_mint_data(
        mint_authority: Optional[str],
        supply: int,
        decimals: int,
        is_initialized: bool = True,
        freeze_authority: Optional[str] = None,
        transfer_fee_config: Optional[TransferFeeConfig] = None,
        interest_bearing_config: Optional[InterestBearingConfig] = None,
        metadata: Optional[TokenMetadata] = None,
    ) -> bytes:
        """
        Helper utility to serialize binary on-chain mint data with Token-2022 extensions.
        """
        buf = bytearray()
        buf.extend(_pack_coption_pubkey(mint_authority))
        buf.extend(struct.pack("<QBB", supply, decimals, 1 if is_initialized else 0))
        buf.extend(_pack_coption_pubkey(freeze_authority))

        has_extensions = any([transfer_fee_config, interest_bearing_config, metadata])
        if has_extensions:
            # Pad up to 165 bytes and set AccountType::Mint (1) at byte 165
            if len(buf) < 165:
                buf.extend(b"\x00" * (165 - len(buf)))
            buf.append(1)  # AccountType::Mint

            # Append TransferFeeConfig
            if transfer_fee_config:
                cfg_val = bytearray()
                cfg_val.extend(_pack_coption_pubkey(transfer_fee_config.transfer_fee_config_authority))
                cfg_val.extend(_pack_coption_pubkey(transfer_fee_config.withdraw_withheld_authority))
                cfg_val.extend(struct.pack("<Q", transfer_fee_config.withheld_amount))
                # Older
                cfg_val.extend(
                    struct.pack(
                        "<QH6sQ",
                        transfer_fee_config.older_transfer_fee.epoch,
                        transfer_fee_config.older_transfer_fee.transfer_fee_basis_points,
                        b"\x00" * 6,
                        transfer_fee_config.older_transfer_fee.maximum_fee,
                    )
                )
                # Newer
                cfg_val.extend(
                    struct.pack(
                        "<QH6sQ",
                        transfer_fee_config.newer_transfer_fee.epoch,
                        transfer_fee_config.newer_transfer_fee.transfer_fee_basis_points,
                        b"\x00" * 6,
                        transfer_fee_config.newer_transfer_fee.maximum_fee,
                    )
                )
                buf.extend(struct.pack("<HH", ExtensionType.TransferFeeConfig, len(cfg_val)))
                buf.extend(cfg_val)

            # Append InterestBearingConfig
            if interest_bearing_config:
                ib_val = bytearray()
                ib_val.extend(b58decode(interest_bearing_config.rate_authority))
                ib_val.extend(
                    struct.pack(
                        "<qhqh",
                        interest_bearing_config.initialization_timestamp,
                        interest_bearing_config.pre_update_average_rate,
                        interest_bearing_config.last_update_timestamp,
                        interest_bearing_config.current_rate,
                    )
                )
                buf.extend(struct.pack("<HH", ExtensionType.InterestBearingConfig, len(ib_val)))
                buf.extend(ib_val)

            # Append TokenMetadata
            if metadata:
                m_val = bytearray()
                m_val.extend(_pack_coption_pubkey(metadata.update_authority))
                m_val.extend(b58decode(metadata.mint))
                m_val.extend(_pack_borsh_string(metadata.name))
                m_val.extend(_pack_borsh_string(metadata.symbol))
                m_val.extend(_pack_borsh_string(metadata.uri))
                m_val.extend(struct.pack("<I", len(metadata.additional_metadata)))
                for k, v in metadata.additional_metadata.items():
                    m_val.extend(_pack_borsh_string(k))
                    m_val.extend(_pack_borsh_string(v))
                buf.extend(struct.pack("<HH", ExtensionType.TokenMetadata, len(m_val)))
                buf.extend(m_val)

        return bytes(buf)

    @staticmethod
    def encode_token_account_data(
        mint: str,
        owner: str,
        amount: int,
        delegate: Optional[str] = None,
        state: int = 1,
        is_native_lamports: Optional[int] = None,
        delegated_amount: int = 0,
        close_authority: Optional[str] = None,
        transfer_fee_amount: Optional[int] = None,
    ) -> bytes:
        """
        Helper utility to serialize binary on-chain token account data with Token-2022 extensions.
        """
        buf = bytearray()
        buf.extend(b58decode(mint))
        buf.extend(b58decode(owner))
        buf.extend(struct.pack("<Q", amount))
        buf.extend(_pack_coption_pubkey(delegate))
        buf.append(state)

        if is_native_lamports is not None:
            buf.extend(struct.pack("<IQ", 1, is_native_lamports))
        else:
            buf.extend(struct.pack("<IQ", 0, 0))

        buf.extend(struct.pack("<Q", delegated_amount))
        buf.extend(_pack_coption_pubkey(close_authority))

        if transfer_fee_amount is not None:
            buf.append(2)  # AccountType::Account
            fee_val = struct.pack("<Q", transfer_fee_amount)
            buf.extend(struct.pack("<HH", ExtensionType.TransferFeeAmount, len(fee_val)))
            buf.extend(fee_val)

        return bytes(buf)

    @classmethod
    def to_uvix_slug(cls, target: Union[SPLTokenMint, SPLTokenAccount]) -> str:
        """Wraps SPLTokenMint or SPLTokenAccount into a standard UVIX envelope."""
        return target.to_uvix_slug()
