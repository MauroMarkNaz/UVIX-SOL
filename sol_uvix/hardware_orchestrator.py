"""
Unified Hardware Workload Orchestrator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Routes tasks across the heterogeneous hardware split:
- Text / Token generation / Embeddings -> AMD XDNA 2 NPU (50 TOPS)
- Video Transcoding (NVENC/NVDEC) -> NVIDIA GeForce RTX 4070
- Raster Graphics / Compute -> NVIDIA GeForce RTX 4070
Emits canonical UVIX-RI-1.0 envelopes for multi-agent mesh synchronization.
"""

from typing import Dict, Any, Optional
from .npu_engine import NPUTextEngine
from .gpu_pipeline import GPUVideoRasterPipeline
from .codec import encode_uvix_slug


class HardwareWorkloadOrchestrator:
    """
    Central dispatcher managing the heterogeneous split between
    AMD Ryzen AI NPU and NVIDIA discrete GPU.
    """

    def __init__(self):
        self.npu = NPUTextEngine()
        self.gpu = GPUVideoRasterPipeline()

    def dispatch(self, workload_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatches workload to the appropriate hardware unit:
        - 'text' or 'nlp' -> NPU
        - 'video' or 'transcode' -> GPU (NVENC/NVDEC)
        - 'raster' or 'render' -> GPU (Direct3D12/Vulkan)
        """
        wtype = workload_type.lower()
        if wtype in ("text", "nlp", "embedding", "llm"):
            prompt = params.get("prompt", "Solana UVIX state payload")
            max_tokens = params.get("max_tokens", 128)
            result = self.npu.process_text_task(prompt, max_tokens=max_tokens)
            result["slug"] = self.npu.to_uvix_slug(result)
            return result

        elif wtype in ("video", "transcode", "encode", "decode"):
            codec = params.get("codec", "hevc_nvenc")
            resolution = params.get("resolution", "1080p")
            frames = params.get("frames", 300)
            result = self.gpu.process_video_transcode(codec=codec, resolution=resolution, frame_count=frames)
            result["slug"] = self.gpu.to_uvix_slug(result)
            return result

        elif wtype in ("raster", "render", "graphics", "3d"):
            primitives = params.get("primitives", 50_000)
            resolution = params.get("resolution", "2560x1440")
            result = self.gpu.process_raster_render(primitive_count=primitives, resolution=resolution)
            result["slug"] = self.gpu.to_uvix_slug(result)
            return result

        else:
            raise ValueError(f"Unknown workload type: '{workload_type}'. Expected 'text', 'video', or 'raster'.")

    def get_hardware_status(self) -> Dict[str, Any]:
        """Returns live hardware allocation and configuration status."""
        return {
            "npu": {
                "device": self.npu.device_name,
                "backend": self.npu.backend,
                "driver": "IpuMcdmDriver (MCDDM)",
                "tops": 50.0,
                "role": "Text Off-Ramping & LLM Token Generation",
            },
            "gpu": {
                "device": self.gpu.gpu_name,
                "driver": self.gpu.driver_version,
                "vram_total_mb": self.gpu.vram_total,
                "vram_used_mb": self.gpu.vram_used,
                "role": "Video Transcoding (NVENC/NVDEC) & Raster Rendering",
            },
            "split_policy": "NPU_TEXT_GPU_VIDEO_RASTER",
            "protocol": "UVIX-RI-1.0",
        }
