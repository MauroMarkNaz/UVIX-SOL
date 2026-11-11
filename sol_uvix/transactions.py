"""
Solana VersionedTransaction and Address Lookup Table (ALT) Parser
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Handles decoding and serialization of Solana transactions:
- Version 0 (v0) transactions with Address Lookup Tables (ALTs)
- Legacy transactions
- Instruction decoding with signer/writable permission resolution
- Address Lookup Table account binary parser
- ComputeBudget instruction decoding & priority fee calculations
- Canonical UVIX slug encapsulation (UVIX-RI-1.0)
"""

import struct
import base64
import time
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass, field, asdict

from .codec import encode_uvix_slug, decode_uvix_slug, compute_canonical_payload_hash

# Solana Well-Known Program IDs
COMPUTE_BUDGET_PROGRAM_ID = "ComputeBudget111111111111111111111111111111"
ADDRESS_LOOKUP_TABLE_PROGRAM_ID = "AddressLookupTab1e1111111111111111111111111"
SYSTEM_PROGRAM_ID = "11111111111111111111111111111111"

DEFAULT_COMPUTE_UNIT_LIMIT = 200_000
LOOKUP_TABLE_META_SIZE = 56

# Base58 Alphabet
B58_CHARS = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58encode(b: bytes) -> str:
    """Encodes bytes into a Base58 string."""
    n = int.from_bytes(b, "big")
    res = []
    while n > 0:
        n, r = divmod(n, 58)
        res.append(B58_CHARS[r])
    pad = 0
    for byte in b:
        if byte == 0:
            pad += 1
        else:
            break
    return ("1" * pad) + "".join(reversed(res))


def b58decode(s: str) -> bytes:
    """Decodes a Base58 string into bytes."""
    n = 0
    for char in s:
        idx = B58_CHARS.find(char)
        if idx == -1:
            raise ValueError(f"Invalid Base58 character: '{char}'")
        n = n * 58 + idx
    pad = 0
    for char in s:
        if char == "1":
            pad += 1
        else:
            break
    res = n.to_bytes((n.bit_length() + 7) // 8, "big") if n > 0 else b""
    return (b"\x00" * pad) + res


def encode_compact_u16(val: int) -> bytes:
    """Encodes an integer as Solana short_vec / compact-u16."""
    res = bytearray()
    rem = val
    while True:
        elem = rem & 0x7F
        rem >>= 7
        if rem == 0:
            res.append(elem)
            break
        else:
            elem |= 0x80
            res.append(elem)
    return bytes(res)


def decode_compact_u16(buf: bytes, offset: int = 0) -> Tuple[int, int]:
    """Decodes a Solana compact-u16 from buffer at offset, returns (value, new_offset)."""
    val = 0
    shift = 0
    pos = offset
    while True:
        if pos >= len(buf):
            raise ValueError("Buffer underflow while decoding compact-u16")
        byte = buf[pos]
        pos += 1
        val |= (byte & 0x7F) << shift
        if (byte & 0x80) == 0:
            break
        shift += 7
        if shift > 21:
            raise ValueError("Invalid compact-u16 representation (exceeds 3 bytes)")
    return val, pos


@dataclass
class MessageHeader:
    """Transaction message header describing account permission counts."""
    num_required_signatures: int
    num_readonly_signed_accounts: int
    num_readonly_unsigned_accounts: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CompiledInstruction:
    """Instruction compiled into index references."""
    program_id_index: int
    accounts: List[int]
    data: bytes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "program_id_index": self.program_id_index,
            "accounts": self.accounts,
            "data_hex": self.data.hex(),
            "data_base64": base64.b64encode(self.data).decode("utf-8"),
        }


@dataclass
class AddressTableLookup:
    """Lookup table reference in a v0 transaction."""
    account_key: str  # Base58 public key of the ALT account
    writable_indexes: List[int]
    readonly_indexes: List[int]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AddressLookupTableAccount:
    """On-chain Address Lookup Table account state."""
    key: str
    deactivation_slot: int
    last_extended_slot: int
    last_extended_slot_start_index: int
    authority: Optional[str]
    addresses: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def decode(cls, data: bytes, key: str = "") -> "AddressLookupTableAccount":
        """
        Parses raw on-chain binary data for an Address Lookup Table account.
        Layout (56-byte header followed by sequence of 32-byte public keys):
        - Optional 4-byte ProgramState enum discriminator (1 = LookupTable)
        - LookupTableMeta:
            deactivation_slot: u64
            last_extended_slot: u64
            last_extended_slot_start_index: u8
            authority: Option<Pubkey> (1 byte tag + 32 bytes)
            padding: u16
        - Contiguous sequence of 32-byte public keys
        """
        if len(data) < LOOKUP_TABLE_META_SIZE:
            raise ValueError(f"Data length {len(data)} too small for Address Lookup Table")

        has_enum_tag = struct.unpack_from("<I", data, 0)[0] == 1
        if has_enum_tag:
            # 4-byte enum discriminator at 0..4, meta ends at 56
            meta_offset = 4
            addresses_offset = LOOKUP_TABLE_META_SIZE
        else:
            meta_offset = 0
            addresses_offset = LOOKUP_TABLE_META_SIZE

        (
            deactivation_slot,
            last_extended_slot,
            last_extended_slot_start_index,
        ) = struct.unpack_from("<QQB", data, meta_offset)

        auth_tag_idx = meta_offset + 17
        has_auth = data[auth_tag_idx] != 0 if auth_tag_idx < len(data) else False
        if has_auth and len(data) >= auth_tag_idx + 33:
            authority = b58encode(data[auth_tag_idx + 1 : auth_tag_idx + 33])
        else:
            authority = None

        addresses = []
        for i in range(addresses_offset, len(data) - (len(data) - addresses_offset) % 32, 32):
            pubkey_bytes = data[i : i + 32]
            addresses.append(b58encode(pubkey_bytes))

        return cls(
            key=key,
            deactivation_slot=deactivation_slot,
            last_extended_slot=last_extended_slot,
            last_extended_slot_start_index=last_extended_slot_start_index,
            authority=authority,
            addresses=addresses,
        )

    def to_uvix_slug(self) -> str:
        payload = {
            "protocol": "solana-alt",
            "type": "address_lookup_table",
            "data": self.to_dict(),
        }
        return encode_uvix_slug(
            payload,
            source_platform="Solana-ALT",
            target_platform="UVIX-Mesh-MultiAgent",
            compatibility_layer="solana-alt-uvix-v1",
        )


@dataclass
class InstructionAccount:
    """Resolved account metadata for an instruction."""
    pubkey: str
    is_signer: bool
    is_writable: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DecodedInstruction:
    """Human-readable decoded instruction with resolved addresses."""
    program_id: str
    accounts: List[InstructionAccount]
    data: bytes
    parsed_type: Optional[str] = None
    parsed_info: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "program_id": self.program_id,
            "accounts": [acc.to_dict() for acc in self.accounts],
            "data_hex": self.data.hex(),
            "data_base64": base64.b64encode(self.data).decode("utf-8"),
            "parsed_type": self.parsed_type,
            "parsed_info": self.parsed_info,
        }


@dataclass
class ComputeBudgetInfo:
    """Extracted compute budget configuration and priority fee."""
    unit_limit: Optional[int] = None
    unit_price_micro_lamports: Optional[int] = None
    heap_frame_bytes: Optional[int] = None
    loaded_accounts_data_size_limit: Optional[int] = None
    priority_fee_lamports: int = 0
    priority_fee_sol: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VersionedTransaction:
    """
    Solana Versioned Transaction (v0 or Legacy).
    Enables inspection of signatures, static and dynamic ALT accounts,
    compiled instructions, compute budget, and UVIX encapsulation.
    """
    version: Union[int, str]  # 0 for v0, "legacy" for legacy
    signatures: List[str]
    header: MessageHeader
    account_keys: List[str]
    recent_blockhash: str
    instructions: List[CompiledInstruction]
    address_table_lookups: List[AddressTableLookup] = field(default_factory=list)
    resolved_account_keys: Optional[List[str]] = None
    compute_budget: Optional[ComputeBudgetInfo] = None
    decoded_instructions: Optional[List[DecodedInstruction]] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "signatures": self.signatures,
            "header": self.header.to_dict(),
            "account_keys": self.account_keys,
            "recent_blockhash": self.recent_blockhash,
            "instructions": [instr.to_dict() for instr in self.instructions],
            "address_table_lookups": [lut.to_dict() for lut in self.address_table_lookups],
            "resolved_account_keys": self.resolved_account_keys,
            "compute_budget": self.compute_budget.to_dict() if self.compute_budget else None,
            "decoded_instructions": [di.to_dict() for di in self.decoded_instructions] if self.decoded_instructions else None,
            "timestamp": self.timestamp,
        }

    @property
    def is_versioned(self) -> bool:
        return self.version != "legacy"

    @classmethod
    def from_bytes(cls, raw: bytes) -> "VersionedTransaction":
        """Deserializes raw binary wire format transaction."""
        num_sigs, offset = decode_compact_u16(raw, 0)
        signatures = []
        for _ in range(num_sigs):
            if offset + 64 > len(raw):
                raise ValueError("Buffer underflow reading transaction signature")
            sig_bytes = raw[offset : offset + 64]
            signatures.append(b58encode(sig_bytes))
            offset += 64

        if offset >= len(raw):
            raise ValueError("Buffer underflow before transaction message")

        first_byte = raw[offset]
        is_versioned = (first_byte & 0x80) != 0

        if is_versioned:
            version: Union[int, str] = first_byte & 0x7F
            offset += 1
            if offset + 3 > len(raw):
                raise ValueError("Buffer underflow reading v0 message header")
            num_req_sigs, num_ro_signed, num_ro_unsigned = struct.unpack_from("<BBB", raw, offset)
            offset += 3
        else:
            version = "legacy"
            if offset + 3 > len(raw):
                raise ValueError("Buffer underflow reading legacy message header")
            num_req_sigs, num_ro_signed, num_ro_unsigned = struct.unpack_from("<BBB", raw, offset)
            offset += 3

        header = MessageHeader(
            num_required_signatures=num_req_sigs,
            num_readonly_signed_accounts=num_ro_signed,
            num_readonly_unsigned_accounts=num_ro_unsigned,
        )

        # Static account keys
        num_static_accounts, offset = decode_compact_u16(raw, offset)
        account_keys = []
        for _ in range(num_static_accounts):
            if offset + 32 > len(raw):
                raise ValueError("Buffer underflow reading account key")
            account_keys.append(b58encode(raw[offset : offset + 32]))
            offset += 32

        # Recent blockhash
        if offset + 32 > len(raw):
            raise ValueError("Buffer underflow reading recent blockhash")
        recent_blockhash = b58encode(raw[offset : offset + 32])
        offset += 32

        # Instructions
        num_instructions, offset = decode_compact_u16(raw, offset)
        instructions = []
        for _ in range(num_instructions):
            if offset >= len(raw):
                raise ValueError("Buffer underflow reading instruction program id index")
            program_id_index = raw[offset]
            offset += 1

            num_accounts, offset = decode_compact_u16(raw, offset)
            if offset + num_accounts > len(raw):
                raise ValueError("Buffer underflow reading instruction accounts")
            accounts = list(raw[offset : offset + num_accounts])
            offset += num_accounts

            data_len, offset = decode_compact_u16(raw, offset)
            if offset + data_len > len(raw):
                raise ValueError("Buffer underflow reading instruction data")
            data = raw[offset : offset + data_len]
            offset += data_len

            instructions.append(CompiledInstruction(program_id_index, accounts, data))

        # Address Table Lookups (v0 only)
        address_table_lookups = []
        if is_versioned:
            num_lookups, offset = decode_compact_u16(raw, offset)
            for _ in range(num_lookups):
                if offset + 32 > len(raw):
                    raise ValueError("Buffer underflow reading ALT pubkey")
                lut_key = b58encode(raw[offset : offset + 32])
                offset += 32

                num_w, offset = decode_compact_u16(raw, offset)
                writable_indexes = list(raw[offset : offset + num_w])
                offset += num_w

                num_r, offset = decode_compact_u16(raw, offset)
                readonly_indexes = list(raw[offset : offset + num_r])
                offset += num_r

                address_table_lookups.append(
                    AddressTableLookup(lut_key, writable_indexes, readonly_indexes)
                )

        tx = cls(
            version=version,
            signatures=signatures,
            header=header,
            account_keys=account_keys,
            recent_blockhash=recent_blockhash,
            instructions=instructions,
            address_table_lookups=address_table_lookups,
        )
        tx.extract_compute_budget()
        return tx

    @classmethod
    def from_base64(cls, b64_str: str) -> "VersionedTransaction":
        """Deserializes from a Base64-encoded wire format string."""
        return cls.from_bytes(base64.b64decode(b64_str))

    @classmethod
    def from_base58(cls, b58_str: str) -> "VersionedTransaction":
        """Deserializes from a Base58-encoded wire format string."""
        return cls.from_bytes(b58decode(b58_str))

    @classmethod
    def from_rpc_dict(cls, rpc_dict: Dict[str, Any]) -> "VersionedTransaction":
        """Parses a transaction from standard Solana getTransaction RPC dictionary."""
        tx_dict = rpc_dict.get("transaction", rpc_dict)
        signatures = tx_dict.get("signatures", [])
        msg = tx_dict.get("message", {})

        hdr = msg.get("header", {})
        header = MessageHeader(
            num_required_signatures=hdr.get("numRequiredSignatures", 1),
            num_readonly_signed_accounts=hdr.get("numReadonlySignedAccounts", 0),
            num_readonly_unsigned_accounts=hdr.get("numReadonlyUnsignedAccounts", 0),
        )

        account_keys = msg.get("accountKeys", [])
        recent_blockhash = msg.get("recentBlockhash", "")

        compiled_instructions = []
        for ix in msg.get("instructions", []):
            p_idx = ix.get("programIdIndex", 0)
            accs = ix.get("accounts", [])
            raw_data = ix.get("data", "")
            try:
                data_bytes = b58decode(raw_data)
            except Exception:
                try:
                    data_bytes = base64.b64decode(raw_data)
                except Exception:
                    data_bytes = raw_data.encode("utf-8") if isinstance(raw_data, str) else bytes(raw_data)
            compiled_instructions.append(CompiledInstruction(p_idx, accs, data_bytes))

        address_table_lookups = []
        for lut in msg.get("addressTableLookups", []):
            address_table_lookups.append(
                AddressTableLookup(
                    account_key=lut.get("accountKey", ""),
                    writable_indexes=lut.get("writableIndexes", []),
                    readonly_indexes=lut.get("readonlyIndexes", []),
                )
            )

        version_val = rpc_dict.get("version", 0 if address_table_lookups else "legacy")
        tx = cls(
            version=version_val,
            signatures=signatures,
            header=header,
            account_keys=account_keys,
            recent_blockhash=recent_blockhash,
            instructions=compiled_instructions,
            address_table_lookups=address_table_lookups,
        )
        tx.extract_compute_budget()
        return tx

    def serialize(self) -> bytes:
        """Serializes transaction back to canonical wire format bytes."""
        buf = bytearray()
        buf.extend(encode_compact_u16(len(self.signatures)))
        for sig in self.signatures:
            sig_raw = b58decode(sig) if isinstance(sig, str) else sig
            if len(sig_raw) != 64:
                raise ValueError(f"Signature must be exactly 64 bytes, got {len(sig_raw)}")
            buf.extend(sig_raw)

        # Message
        if self.is_versioned:
            v_num = int(self.version) & 0x7F
            buf.append(0x80 | v_num)

        buf.append(self.header.num_required_signatures)
        buf.append(self.header.num_readonly_signed_accounts)
        buf.append(self.header.num_readonly_unsigned_accounts)

        # Static account keys
        buf.extend(encode_compact_u16(len(self.account_keys)))
        for k in self.account_keys:
            k_raw = b58decode(k) if isinstance(k, str) else k
            if len(k_raw) != 32:
                raise ValueError(f"Account key must be 32 bytes, got {len(k_raw)}")
            buf.extend(k_raw)

        # Recent blockhash
        bh_raw = b58decode(self.recent_blockhash) if isinstance(self.recent_blockhash, str) else self.recent_blockhash
        if len(bh_raw) != 32:
            raise ValueError(f"Blockhash must be 32 bytes, got {len(bh_raw)}")
        buf.extend(bh_raw)

        # Instructions
        buf.extend(encode_compact_u16(len(self.instructions)))
        for instr in self.instructions:
            buf.append(instr.program_id_index)
            buf.extend(encode_compact_u16(len(instr.accounts)))
            buf.extend(bytes(instr.accounts))
            buf.extend(encode_compact_u16(len(instr.data)))
            buf.extend(instr.data)

        # Address Table Lookups (v0 only)
        if self.is_versioned:
            buf.extend(encode_compact_u16(len(self.address_table_lookups)))
            for lut in self.address_table_lookups:
                lut_key_raw = b58decode(lut.account_key) if isinstance(lut.account_key, str) else lut.account_key
                buf.extend(lut_key_raw)
                buf.extend(encode_compact_u16(len(lut.writable_indexes)))
                buf.extend(bytes(lut.writable_indexes))
                buf.extend(encode_compact_u16(len(lut.readonly_indexes)))
                buf.extend(bytes(lut.readonly_indexes))

        return bytes(buf)

    def resolve_addresses(
        self,
        lookup_tables: Union[Dict[str, List[str]], List[AddressLookupTableAccount]],
    ) -> List[str]:
        """
        Resolves full account keys by combining static keys and Address Lookup Tables (ALTs).
        Standard Solana v0 Ordering:
        1. Static account keys
        2. All writable addresses from each lookup table in order
        3. All readonly addresses from each lookup table in order
        """
        lut_dict: Dict[str, List[str]] = {}
        if isinstance(lookup_tables, dict):
            lut_dict = lookup_tables
        else:
            for item in lookup_tables:
                lut_dict[item.key] = item.addresses

        resolved = list(self.account_keys)
        writable_dynamic = []
        readonly_dynamic = []

        for lut in self.address_table_lookups:
            table_addresses = lut_dict.get(lut.account_key, [])
            for idx in lut.writable_indexes:
                if idx < len(table_addresses):
                    writable_dynamic.append(table_addresses[idx])
                else:
                    raise IndexError(f"Writable index {idx} out of range for ALT {lut.account_key}")

            for idx in lut.readonly_indexes:
                if idx < len(table_addresses):
                    readonly_dynamic.append(table_addresses[idx])
                else:
                    raise IndexError(f"Readonly index {idx} out of range for ALT {lut.account_key}")

        resolved.extend(writable_dynamic)
        resolved.extend(readonly_dynamic)
        self.resolved_account_keys = resolved
        return resolved

    def decode_instructions(
        self,
        lookup_tables: Optional[Union[Dict[str, List[str]], List[AddressLookupTableAccount]]] = None,
    ) -> List[DecodedInstruction]:
        """
        Decodes all compiled instructions into high-level DecodedInstruction instances
        with resolved account addresses and permissions (signer, writable).
        """
        if self.resolved_account_keys is None:
            if lookup_tables:
                self.resolve_addresses(lookup_tables)
            else:
                self.resolved_account_keys = list(self.account_keys)

        resolved_keys = self.resolved_account_keys
        num_static = len(self.account_keys)
        num_req_sigs = self.header.num_required_signatures
        num_ro_signed = self.header.num_readonly_signed_accounts
        num_ro_unsigned = self.header.num_readonly_unsigned_accounts

        decoded_list = []
        for ix in self.instructions:
            if ix.program_id_index >= len(resolved_keys):
                raise IndexError(f"Program ID index {ix.program_id_index} out of bounds")
            prog_id = resolved_keys[ix.program_id_index]

            accounts: List[InstructionAccount] = []
            for acc_idx in ix.accounts:
                if acc_idx >= len(resolved_keys):
                    raise IndexError(f"Account index {acc_idx} out of bounds")
                pubkey = resolved_keys[acc_idx]

                is_signer = acc_idx < num_req_sigs
                if is_signer:
                    is_writable = acc_idx < (num_req_sigs - num_ro_signed)
                elif acc_idx < num_static:
                    is_writable = acc_idx < (num_static - num_ro_unsigned)
                else:
                    # In dynamic accounts: writable accounts precede readonly accounts
                    # Determine whether this dynamic index falls within writable lookups
                    num_dynamic_writable = sum(len(l.writable_indexes) for l in self.address_table_lookups)
                    dynamic_offset = acc_idx - num_static
                    is_writable = dynamic_offset < num_dynamic_writable

                accounts.append(InstructionAccount(pubkey=pubkey, is_signer=is_signer, is_writable=is_writable))

            parsed_type = None
            parsed_info = None

            # Detect ComputeBudget program instructions
            if prog_id == COMPUTE_BUDGET_PROGRAM_ID and len(ix.data) > 0:
                disc = ix.data[0]
                if disc == 1 and len(ix.data) >= 5:
                    parsed_type = "ComputeBudget::RequestHeapFrame"
                    parsed_info = {"bytes": struct.unpack_from("<I", ix.data, 1)[0]}
                elif disc == 2 and len(ix.data) >= 5:
                    parsed_type = "ComputeBudget::SetComputeUnitLimit"
                    parsed_info = {"units": struct.unpack_from("<I", ix.data, 1)[0]}
                elif disc == 3 and len(ix.data) >= 9:
                    parsed_type = "ComputeBudget::SetComputeUnitPrice"
                    parsed_info = {"micro_lamports": struct.unpack_from("<Q", ix.data, 1)[0]}
                elif disc == 4 and len(ix.data) >= 5:
                    parsed_type = "ComputeBudget::SetLoadedAccountsDataSizeLimit"
                    parsed_info = {"bytes": struct.unpack_from("<I", ix.data, 1)[0]}

            decoded_list.append(
                DecodedInstruction(
                    program_id=prog_id,
                    accounts=accounts,
                    data=ix.data,
                    parsed_type=parsed_type,
                    parsed_info=parsed_info,
                )
            )

        self.decoded_instructions = decoded_list
        return decoded_list

    def extract_compute_budget(self) -> ComputeBudgetInfo:
        """
        Extracts compute budget limits, priority unit prices, and calculates
        effective priority fee in lamports and SOL.
        """
        unit_limit: Optional[int] = None
        unit_price_micro_lamports: Optional[int] = None
        heap_frame: Optional[int] = None
        loaded_accounts_size: Optional[int] = None

        # Look through all compiled instructions for ComputeBudget program
        for ix in self.instructions:
            if ix.program_id_index < len(self.account_keys):
                prog_id = self.account_keys[ix.program_id_index]
                if prog_id == COMPUTE_BUDGET_PROGRAM_ID and len(ix.data) > 0:
                    disc = ix.data[0]
                    if disc == 1 and len(ix.data) >= 5:
                        heap_frame = struct.unpack_from("<I", ix.data, 1)[0]
                    elif disc == 2 and len(ix.data) >= 5:
                        unit_limit = struct.unpack_from("<I", ix.data, 1)[0]
                    elif disc == 3 and len(ix.data) >= 9:
                        unit_price_micro_lamports = struct.unpack_from("<Q", ix.data, 1)[0]
                    elif disc == 4 and len(ix.data) >= 5:
                        loaded_accounts_size = struct.unpack_from("<I", ix.data, 1)[0]

        # Calculate priority fee
        priority_fee_lamports = 0
        if unit_price_micro_lamports is not None:
            effective_limit = unit_limit if unit_limit is not None else DEFAULT_COMPUTE_UNIT_LIMIT
            priority_fee_lamports = (effective_limit * unit_price_micro_lamports) // 1_000_000

        priority_fee_sol = priority_fee_lamports / 1_000_000_000.0

        info = ComputeBudgetInfo(
            unit_limit=unit_limit,
            unit_price_micro_lamports=unit_price_micro_lamports,
            heap_frame_bytes=heap_frame,
            loaded_accounts_data_size_limit=loaded_accounts_size,
            priority_fee_lamports=priority_fee_lamports,
            priority_fee_sol=priority_fee_sol,
        )
        self.compute_budget = info
        return info

    def to_uvix_slug(self) -> str:
        """
        Encapsulates the versioned transaction telemetry into a standard UVIX-RI-1.0 slug envelope.
        """
        # Ensure compute budget and decoded instructions are populated
        if self.compute_budget is None:
            self.extract_compute_budget()
        if self.decoded_instructions is None and self.resolved_account_keys:
            self.decode_instructions()

        payload = {
            "protocol": "solana-transaction-v0" if self.is_versioned else "solana-transaction-legacy",
            "type": "versioned_transaction",
            "data": self.to_dict(),
        }
        return encode_uvix_slug(
            payload,
            source_platform="Solana-Tx-Engine",
            target_platform="UVIX-Mesh-MultiAgent",
            compatibility_layer="solana-transaction-uvix-v1",
        )
