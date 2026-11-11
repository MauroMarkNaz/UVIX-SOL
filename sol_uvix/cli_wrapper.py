"""
Solana CLI Wrapper with Canonical UVIX Encapsulation (UVIX-RI-1.0)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Interfaces with the local Solana CLI / Agave installation (supporting
Windows host shims and native WSL Ubuntu-24.04 environments), querying
balance, airdrop, configuration, and cluster status, and wrapping the
resulting telemetry into canonical UVIX slug envelopes.
"""

import json
import logging
import os
import platform
import re
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from .codec import encode_uvix_slug, decode_uvix_slug, UVIXSlug

logger = logging.getLogger("sol_uvix.cli_wrapper")


class SolanaCLIError(Exception):
    """Raised when a Solana CLI execution fails."""

    def __init__(self, message: str, returncode: int = 1, stdout: str = "", stderr: str = ""):
        super().__init__(message)
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class SolanaCLIWrapper:
    """
    High-level interface to the local Solana / Agave CLI binary.
    Provides methods for balance queries, airdrop requests, config inspection,
    and cluster status tracking, producing canonical UVIX-RI-1.0 slug envelopes.
    """

    def __init__(
        self,
        cli_path: Optional[str] = None,
        wsl_distro: Optional[str] = "Ubuntu-24.04",
        timeout: float = 30.0,
    ):
        self.cli_path = cli_path or os.environ.get("SOLANA_CLI_PATH")
        self.wsl_distro = wsl_distro
        self.timeout = timeout
        self._cmd_prefix = self._resolve_cli_command()

    def _resolve_cli_command(self) -> List[str]:
        """
        Detects available Solana CLI binary.
        Checks explicit path, PATH environment, Windows shims, and WSL.
        """
        if self.cli_path:
            return [self.cli_path]

        # 1. Check system PATH
        found = shutil.which("solana")
        if found:
            return [found]

        # 2. Check platform-specific active release directories
        is_windows = platform.system() == "Windows"
        user_home = os.path.expanduser("~")
        linux_default = os.path.join(user_home, ".local", "share", "solana", "install", "active_release", "bin", "solana")

        if not is_windows and os.path.isfile(linux_default) and os.access(linux_default, os.X_OK):
            return [linux_default]

        if is_windows:
            # Check if WSL is available with solana installed
            wsl_bin = shutil.which("wsl")
            if wsl_bin:
                distro_arg = ["-d", self.wsl_distro] if self.wsl_distro else []
                # Check if solana is accessible in WSL
                try:
                    res = subprocess.run(
                        [wsl_bin, *distro_arg, "--", "bash", "-c", "which solana || test -x $HOME/.local/share/solana/install/active_release/bin/solana"],
                        capture_output=True,
                        text=True,
                        timeout=5.0,
                    )
                    if res.returncode == 0:
                        # Return WSL execution prefix
                        wsl_solana_path = res.stdout.strip()
                        if not wsl_solana_path or "solana" not in wsl_solana_path:
                            wsl_solana_path = "$HOME/.local/share/solana/install/active_release/bin/solana"
                        wsl_probe = subprocess.run([wsl_bin, *distro_arg, "--", "bash", "-c", "which solana || (test -x $HOME/.local/share/solana/install/active_release/bin/solana && echo $HOME/.local/share/solana/install/active_release/bin/solana)"], capture_output=True, text=True, timeout=5.0)
                        resolved = wsl_probe.stdout.strip().splitlines()[-1].strip() if wsl_probe.stdout.strip() else ""
                        if resolved and "solana" in resolved:
                            return [wsl_bin, *distro_arg, "--", resolved]
                        return [wsl_bin, *distro_arg, "--", "bash", "-c", f"{wsl_solana_path} \"$@\"", "_"]
                except Exception as e:
                    logger.debug("WSL probe failed: %s", e)

        # Fallback to invoking "solana" directly and relying on PATH
        return ["solana"]

    def execute_raw(self, args: List[str]) -> Tuple[int, str, str]:
        """
        Executes a solana command with the specified arguments.
        Returns (returncode, stdout, stderr).
        """
        cmd = list(self._cmd_prefix) + args
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
            return res.returncode, res.stdout, res.stderr
        except subprocess.TimeoutExpired as e:
            raise SolanaCLIError(
                f"Solana CLI timed out after {self.timeout}s: {' '.join(args)}",
                returncode=-1,
                stdout=(e.stdout or "").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""),
                stderr=(e.stderr or "").decode() if isinstance(e.stderr, bytes) else (e.stderr or ""),
            )
        except FileNotFoundError as e:
            raise SolanaCLIError(f"Solana CLI binary not found: {e}", returncode=-1)

    def get_version(self) -> Dict[str, Any]:
        """
        Queries solana --version and parses client version info.
        Example output: 'solana-cli 4.3.2 (src:4b44ad97; feat:c9ad34d2, client:Agave)'
        """
        code, out, err = self.execute_raw(["--version"])
        if code != 0:
            raise SolanaCLIError(f"Failed to get solana version: {err.strip()}", returncode=code, stdout=out, stderr=err)

        text = out.strip()
        version = text
        client = "Agave" if "Agave" in text else "Solana"
        commit = ""
        feat = ""

        m_version = re.search(r"solana-cli\s+([0-9a-zA-Z.-]+)", text)
        if m_version:
            version = m_version.group(1)
        m_commit = re.search(r"src:([0-9a-fA-F]+)", text)
        if m_commit:
            commit = m_commit.group(1)
        m_feat = re.search(r"feat:([0-9a-fA-F]+)", text)
        if m_feat:
            feat = m_feat.group(1)

        return {
            "raw": text,
            "version": version,
            "client": client,
            "commit": commit,
            "feature_set": feat,
        }

    def get_address(self) -> str:
        """Returns the default configured public key address."""
        code, out, err = self.execute_raw(["address"])
        if code != 0:
            raise SolanaCLIError(f"Failed to get default address: {err.strip()}", returncode=code, stdout=out, stderr=err)
        return out.strip()

    def get_config(self) -> Dict[str, Any]:
        """
        Parses `solana config get`.
        Returns dict with keys: config_file, rpc_url, websocket_url, keypair_path, commitment.
        """
        code, out, err = self.execute_raw(["config", "get"])
        if code != 0:
            raise SolanaCLIError(f"Failed to get solana config: {err.strip()}", returncode=code, stdout=out, stderr=err)

        cfg: Dict[str, Any] = {
            "config_file": "",
            "rpc_url": "",
            "websocket_url": "",
            "keypair_path": "",
            "commitment": "",
        }
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("Config File:"):
                cfg["config_file"] = line.split(":", 1)[1].strip()
            elif line.startswith("RPC URL:"):
                cfg["rpc_url"] = line.split(":", 1)[1].strip()
            elif line.startswith("WebSocket URL:"):
                cfg["websocket_url"] = line.split(":", 1)[1].strip().split()[0]
            elif line.startswith("Keypair Path:"):
                cfg["keypair_path"] = line.split(":", 1)[1].strip()
            elif line.startswith("Commitment:"):
                cfg["commitment"] = line.split(":", 1)[1].strip()

        return cfg

    def set_cluster(self, cluster_or_url: str) -> Dict[str, Any]:
        """
        Configures the target cluster RPC endpoint.
        Recognizes 'devnet', 'mainnet-beta', 'testnet', 'localhost', or custom URLs.
        """
        target = cluster_or_url.strip().lower()
        if target in ("devnet", "d", "-ud"):
            args = ["config", "set", "-ud"]
        elif target in ("mainnet", "mainnet-beta", "m", "-um"):
            args = ["config", "set", "-um"]
        elif target in ("testnet", "t", "-ut"):
            args = ["config", "set", "-ut"]
        elif target in ("localhost", "local", "l", "-ul"):
            args = ["config", "set", "-ul"]
        else:
            args = ["config", "set", "--url", cluster_or_url]

        code, out, err = self.execute_raw(args)
        if code != 0:
            raise SolanaCLIError(f"Failed to set cluster '{cluster_or_url}': {err.strip()}", returncode=code, stdout=out, stderr=err)

        return self.get_config()

    def get_balance(self, pubkey: Optional[str] = None) -> Dict[str, Any]:
        """
        Queries SOL balance for pubkey (or default configured keypair).
        Returns dict with lamports, sol, and pubkey.
        """
        args = ["--output", "json", "balance"]
        if pubkey:
            args.append(pubkey)

        code, out, err = self.execute_raw(args)
        if code != 0:
            # Fallback to standard balance command if --output json is not supported
            raw_args = ["balance"]
            if pubkey:
                raw_args.append(pubkey)
            code, out, err = self.execute_raw(raw_args)
            if code != 0:
                raise SolanaCLIError(f"Failed to get balance: {err.strip()}", returncode=code, stdout=out, stderr=err)

            m = re.search(r"([0-9.]+)\s+SOL", out)
            sol = float(m.group(1)) if m else 0.0
            lamports = int(sol * 1_000_000_000)
            target_pubkey = pubkey or self.get_address()
            return {
                "pubkey": target_pubkey,
                "lamports": lamports,
                "sol": sol,
            }

        try:
            parsed = json.loads(out)
            lamports = parsed.get("lamports", 0)
            target_pubkey = pubkey or self.get_address()
            return {
                "pubkey": target_pubkey,
                "lamports": lamports,
                "sol": lamports / 1_000_000_000.0,
            }
        except Exception:
            m = re.search(r"([0-9.]+)\s+SOL", out)
            sol = float(m.group(1)) if m else 0.0
            return {
                "pubkey": pubkey or self.get_address(),
                "lamports": int(sol * 1_000_000_000),
                "sol": sol,
            }

    def request_airdrop(self, amount: float = 1.0, pubkey: Optional[str] = None) -> Dict[str, Any]:
        """
        Requests an airdrop on devnet/testnet clusters.
        Returns status dictionary including transaction signature when successful.
        """
        target_pubkey = pubkey or self.get_address()
        args = ["airdrop", str(amount)]
        if pubkey:
            args.append(pubkey)

        code, out, err = self.execute_raw(args)
        combined = f"{out}\n{err}".strip()
        success = (code == 0)

        # Extract transaction signature if available (base58 string, ~87-88 chars)
        sig_match = re.search(r"([1-9A-HJ-NP-za-km-z]{64,88})", out)
        signature = sig_match.group(1) if sig_match else None

        return {
            "recipient": target_pubkey,
            "amount_sol": amount,
            "success": success,
            "signature": signature,
            "message": combined,
        }

    def get_cluster_version(self) -> str:
        """Returns the cluster version reported by the connected RPC."""
        code, out, err = self.execute_raw(["cluster-version"])
        if code != 0:
            raise SolanaCLIError(f"Failed to get cluster version: {err.strip()}", returncode=code, stdout=out, stderr=err)
        return out.strip()

    def get_epoch_info(self) -> Dict[str, Any]:
        """
        Queries current epoch, slot, block height, and progress.
        """
        code, out, err = self.execute_raw(["--output", "json", "epoch-info"])
        if code == 0:
            try:
                return json.loads(out)
            except Exception:
                pass

        # Text parsing fallback
        code, out, err = self.execute_raw(["epoch-info"])
        if code != 0:
            raise SolanaCLIError(f"Failed to get epoch info: {err.strip()}", returncode=code, stdout=out, stderr=err)

        info: Dict[str, Any] = {}
        for line in out.splitlines():
            line = line.strip()
            if ":" in line:
                k, v = line.split(":", 1)
                info[k.strip().lower().replace(" ", "_")] = v.strip()
        return info

    def get_cluster_status(self) -> Dict[str, Any]:
        """
        Aggregates cluster status, config, epoch info, and node version.
        """
        config = self.get_config()
        cluster_version = ""
        epoch_info: Dict[str, Any] = {}

        try:
            cluster_version = self.get_cluster_version()
        except Exception as e:
            cluster_version = f"error: {e}"

        try:
            epoch_info = self.get_epoch_info()
        except Exception as e:
            epoch_info = {"error": str(e)}

        return {
            "rpc_url": config.get("rpc_url", ""),
            "websocket_url": config.get("websocket_url", ""),
            "commitment": config.get("commitment", ""),
            "cluster_version": cluster_version,
            "epoch_info": epoch_info,
            "timestamp": time.time(),
        }

    # -------------------------------------------------------------------------
    # Canonical UVIX-RI-1.0 Envelope Framing
    # -------------------------------------------------------------------------

    def wrap_uvix_slug(
        self,
        payload_type: str,
        data: Dict[str, Any],
        source_platform: str = "Solana-CLI",
        target_platform: str = "UVIX-Mesh-MultiAgent",
    ) -> str:
        """
        Wraps command telemetry into a canonical UVIX::<base64>::END envelope
        with SHA-256 payload integrity hashing.
        """
        payload = {
            "protocol": "solana-cli",
            "type": payload_type,
            "timestamp": time.time(),
            "data": data,
        }
        return encode_uvix_slug(
            payload,
            source_platform=source_platform,
            target_platform=target_platform,
            compatibility_layer="solana-uvix-v1",
        )

    def get_address_slug(self) -> str:
        """Fetches the default signer address wrapped in a UVIX slug."""
        addr = self.get_address()
        return self.wrap_uvix_slug("address", {"address": addr})

    def get_config_slug(self) -> str:
        """Fetches CLI cluster and keypair configuration wrapped in a UVIX slug."""
        cfg = self.get_config()
        return self.wrap_uvix_slug("config", cfg)

    def get_balance_slug(self, pubkey: Optional[str] = None) -> str:
        """Fetches SOL balance wrapped in a canonical UVIX slug."""
        bal = self.get_balance(pubkey)
        return self.wrap_uvix_slug("balance", bal)

    def request_airdrop_slug(self, amount: float = 1.0, pubkey: Optional[str] = None) -> str:
        """Requests an airdrop and wraps the result in a canonical UVIX slug."""
        result = self.request_airdrop(amount, pubkey)
        return self.wrap_uvix_slug("airdrop", result)

    def get_cluster_status_slug(self) -> str:
        """Fetches aggregated cluster status wrapped in a canonical UVIX slug."""
        status = self.get_cluster_status()
        return self.wrap_uvix_slug("cluster_status", status)

    def get_epoch_info_slug(self) -> str:
        """Fetches current epoch info wrapped in a canonical UVIX slug."""
        epoch = self.get_epoch_info()
        return self.wrap_uvix_slug("epoch_info", epoch)
