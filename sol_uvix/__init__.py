"""
SOL-UVIX Protocol Suite & Neural Mesh Facade
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Solana Stack, UVIX-RI-1.0 Interoperability Protocol Bridge, Heterogeneous
Hardware Offload, and Edge Neural Mesh Routing.
"""

__version__ = "1.0.0"
__protocol__ = "UVIX-RI-1.0"

from .codec import (
    UVIXSlug,
    encode_uvix_slug,
    decode_uvix_slug,
    compute_canonical_payload_hash,
    UVIXIntegrityError,
    UVIXFormatError,
)
from .models import (
    SolanaAccountState,
    SolanaTransactionState,
    PumpFunBondingCurveState,
    RaydiumPoolState,
    AgentHandoffPayload,
)
from .pumpfun import PumpFunDecoder
from .raydium import RaydiumDecoder
from .client import SolanaUVIXClient
from .ws_client import SolanaUVIXWebSocketClient
from .bridge import UVIXEdgeBridge
from .cli_wrapper import SolanaCLIWrapper, SolanaCLIError
from .transactions import (
    VersionedTransaction,
    MessageHeader,
    CompiledInstruction,
    AddressTableLookup,
    AddressLookupTableAccount,
    InstructionAccount,
    DecodedInstruction,
    ComputeBudgetInfo,
    b58encode,
    b58decode,
    encode_compact_u16,
    decode_compact_u16,
    COMPUTE_BUDGET_PROGRAM_ID,
    ADDRESS_LOOKUP_TABLE_PROGRAM_ID,
    SYSTEM_PROGRAM_ID,
)
from .tokens import (
    SPLTokenMint,
    SPLTokenAccount,
    SPLTokenDecoder,
    ExtensionType,
    TransferFee,
    TransferFeeConfig,
    InterestBearingConfig,
    TokenMetadata,
    MetadataPointer,
    TOKEN_PROGRAM_ID,
    TOKEN_2022_PROGRAM_ID,
    ASSOCIATED_TOKEN_PROGRAM_ID,
)
from .hardware_orchestrator import HardwareWorkloadOrchestrator
from .npu_engine import NPUTextEngine
from .gpu_pipeline import GPUVideoRasterPipeline
from core.mesh import NeuralMeshRouter, EdgeNetwork, MeshNode, NodeType

__all__ = [
    # Codec & Models
    "UVIXSlug",
    "encode_uvix_slug",
    "decode_uvix_slug",
    "compute_canonical_payload_hash",
    "UVIXIntegrityError",
    "UVIXFormatError",
    "SolanaAccountState",
    "SolanaTransactionState",
    "PumpFunBondingCurveState",
    "RaydiumPoolState",
    "AgentHandoffPayload",
    # Decoders & Client
    "PumpFunDecoder",
    "RaydiumDecoder",
    "SolanaUVIXClient",
    "SolanaUVIXWebSocketClient",
    "UVIXEdgeBridge",
    "SolanaCLIWrapper",
    "SolanaCLIError",
    # Transactions & ALTs
    "VersionedTransaction",
    "MessageHeader",
    "CompiledInstruction",
    "AddressTableLookup",
    "AddressLookupTableAccount",
    "InstructionAccount",
    "DecodedInstruction",
    "ComputeBudgetInfo",
    "b58encode",
    "b58decode",
    "encode_compact_u16",
    "decode_compact_u16",
    "COMPUTE_BUDGET_PROGRAM_ID",
    "ADDRESS_LOOKUP_TABLE_PROGRAM_ID",
    "SYSTEM_PROGRAM_ID",
    # Tokens & Token-2022
    "SPLTokenMint",
    "SPLTokenAccount",
    "SPLTokenDecoder",
    "ExtensionType",
    "TransferFee",
    "TransferFeeConfig",
    "InterestBearingConfig",
    "TokenMetadata",
    "MetadataPointer",
    "TOKEN_PROGRAM_ID",
    "TOKEN_2022_PROGRAM_ID",
    "ASSOCIATED_TOKEN_PROGRAM_ID",
    # Hardware Offload
    "HardwareWorkloadOrchestrator",
    "NPUTextEngine",
    "GPUVideoRasterPipeline",
    # Neural Mesh Topology
    "NeuralMeshRouter",
    "EdgeNetwork",
    "MeshNode",
    "NodeType",
]
