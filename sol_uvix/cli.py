"""
SOL-UVIX Command Line Interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
CLI utility to inspect, encode, decode, and verify UVIX envelopes.
"""

import sys
import json
import argparse
from .codec import encode_uvix_slug, decode_uvix_slug, UVIXIntegrityError, UVIXFormatError
from .client import SolanaUVIXClient
from .cli_wrapper import SolanaCLIWrapper, SolanaCLIError
from .transactions import VersionedTransaction
from .tokens import SPLTokenDecoder


def main():
    parser = argparse.ArgumentParser(
        prog="sol-uvix",
        description="Solana Stack and UVIX-RI-1.0 Interoperability Protocol CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Encode command
    encode_parser = subparsers.add_parser("encode", help="Encode JSON file or string into UVIX envelope")
    encode_parser.add_argument("input", help="JSON string or path to JSON file")
    encode_parser.add_argument("--source", default="Solana-CLI", help="Source platform identifier")
    encode_parser.add_argument("--target", default="UVIX-Mesh", help="Target platform identifier")

    # Decode command
    decode_parser = subparsers.add_parser("decode", help="Decode and verify UVIX envelope")
    decode_parser.add_argument("envelope", help="UVIX::<base64>::END envelope string")

    # Account command
    acc_parser = subparsers.add_parser("account", help="Query Solana account and output UVIX slug")
    acc_parser.add_argument("pubkey", help="Solana public key (base58)")
    acc_parser.add_argument("--rpc", default="https://api.mainnet-beta.solana.com", help="RPC URL")

    # CLI Balance command
    bal_parser = subparsers.add_parser("balance", help="Query local Solana CLI balance and output UVIX slug")
    bal_parser.add_argument("pubkey", nargs="?", default=None, help="Optional public key (defaults to active keypair)")
    bal_parser.add_argument("--raw", action="store_true", help="Print raw JSON instead of UVIX envelope")

    # CLI Config command
    cfg_parser = subparsers.add_parser("config", help="Query local Solana CLI config and output UVIX slug")
    cfg_parser.add_argument("--raw", action="store_true", help="Print raw JSON instead of UVIX envelope")

    # CLI Cluster Status command
    status_parser = subparsers.add_parser("status", help="Query cluster status via Solana CLI and output UVIX slug")
    status_parser.add_argument("--raw", action="store_true", help="Print raw JSON instead of UVIX envelope")

    # Transaction command
    tx_parser = subparsers.add_parser("tx", help="Parse versioned/legacy transaction and output UVIX slug")
    tx_parser.add_argument("data", help="Base64 or Base58 encoded wire transaction")
    tx_parser.add_argument("--raw", action="store_true", help="Print raw JSON instead of UVIX envelope")

    # Token command
    token_parser = subparsers.add_parser("token", help="Decode SPL / Token-2022 mint or account base64 buffer")
    token_parser.add_argument("data", help="Base64 encoded account data")
    token_parser.add_argument("--type", choices=["mint", "account"], default="mint", help="Account type")
    token_parser.add_argument("--raw", action="store_true", help="Print raw JSON instead of UVIX envelope")

    args = parser.parse_args()

    if args.command == "encode":
        try:
            try:
                with open(args.input, "r", encoding="utf-8") as f:
                    payload = json.load(f)
            except Exception:
                payload = json.loads(args.input)

            envelope = encode_uvix_slug(payload, source_platform=args.source, target_platform=args.target)
            print(envelope)
        except Exception as e:
            print(f"Error encoding UVIX slug: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "decode":
        try:
            slug = decode_uvix_slug(args.envelope)
            print(json.dumps(slug.to_dict(), indent=2))
        except UVIXIntegrityError as e:
            print(f"INTEGRITY ERROR: {e}", file=sys.stderr)
            sys.exit(2)
        except UVIXFormatError as e:
            print(f"FORMAT ERROR: {e}", file=sys.stderr)
            sys.exit(3)
        except Exception as e:
            print(f"Error decoding: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "account":
        try:
            client = SolanaUVIXClient(rpc_url=args.rpc)
            slug = client.get_account_uvix_slug(args.pubkey)
            if slug:
                print(slug)
            else:
                print(f"Account {args.pubkey} not found", file=sys.stderr)
                sys.exit(1)
        except Exception as e:
            print(f"RPC Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "balance":
        try:
            wrapper = SolanaCLIWrapper()
            if args.raw:
                print(json.dumps(wrapper.get_balance(args.pubkey), indent=2))
            else:
                print(wrapper.get_balance_slug(args.pubkey))
        except SolanaCLIError as e:
            print(f"CLI Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "config":
        try:
            wrapper = SolanaCLIWrapper()
            if args.raw:
                print(json.dumps(wrapper.get_config(), indent=2))
            else:
                print(wrapper.get_config_slug())
        except SolanaCLIError as e:
            print(f"CLI Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "status":
        try:
            wrapper = SolanaCLIWrapper()
            if args.raw:
                print(json.dumps(wrapper.get_cluster_status(), indent=2))
            else:
                print(wrapper.get_cluster_status_slug())
        except SolanaCLIError as e:
            print(f"CLI Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "tx":
        try:
            try:
                tx = VersionedTransaction.from_base64(args.data)
            except Exception:
                tx = VersionedTransaction.from_base58(args.data)

            if args.raw:
                print(json.dumps(tx.to_dict(), indent=2))
            else:
                print(tx.to_uvix_slug())
        except Exception as e:
            print(f"Transaction parsing error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "token":
        try:
            if args.type == "mint":
                state = SPLTokenDecoder.decode_mint_base64(args.data)
            else:
                state = SPLTokenDecoder.decode_token_account_base64(args.data)

            if args.raw:
                print(json.dumps(state.to_dict(), indent=2))
            else:
                print(state.to_uvix_slug())
        except Exception as e:
            print(f"Token decoding error: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
