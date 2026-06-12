"""MDX23C (TFC-TDF v3) drum-kit backend.

Splits a ``drums`` stem into six pieces — kick, snare, toms, hihat, ride,
crash — the only one of our drum models that separates ride from crash. Uses the
vendored TFC-TDF v3 model (``..vendor.mdx23c``, pinned to ZFTurbo v1.0.12) with a
bundled config tied to the pretrained checkpoint; only the large ``.ckpt``
(~438 MB) is fetched at runtime and cached. Inference reuses the shared
chunked-overlap engine :func:`..roformer._demix`.

Checkpoint: "MDX23C DrumSep" by aufr33 & jarredou (SDR ~10.81), fetched from the
``Politrees/UVR_resources`` mirror. The checkpoint labels the hi-hat ``hh``; we
map it to our canonical ``hihat``. Unlike the RoFormer stems this backend needs
only the base ``torch`` stack (no optional ``[roformer]`` extras).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..errors import ModelError, SeparationError
from ..logging_utils import get_logger
from . import download
from .base import ModelInfo, ProgressFn
from .roformer import _demix  # shared chunked-overlap inference engine

if TYPE_CHECKING:  # pragma: no cover - typing only
    import torch

# Canonical pieces this backend emits, in display order. The checkpoint labels
# the hi-hat ``hh``; the other five already match our vocabulary. Also the source
# of truth for this model's ``output_stems``.
MDX23C_DRUM_STEMS = ("kick", "snare", "toms", "hihat", "ride", "crash")

MDX23C_SR = 44100

# Map the checkpoint's source labels to our canonical names (only ``hh`` differs).
_SOURCE_MAP = {
    "kick": "kick",
    "snare": "snare",
    "toms": "toms", "tom": "toms",
    "hh": "hihat", "hihat": "hihat", "hi-hat": "hihat",
    "ride": "ride",
    "crash": "crash",
}

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "vendor" / "mdx23c" / "configs"
_CONFIG_NAME = "config_drumsep_mdx23c.yaml"
_CKPT_NAME = "MDX23C-DrumSep-aufr33-jarredou.ckpt"
_CKPT_URL = (
    "https://huggingface.co/Politrees/UVR_resources/resolve/main/"
    "models/MDX23C/MDX23C-DrumSep-aufr33-jarredou.ckpt"
)


class _DotConfig:
    """Attribute-access wrapper so the vendored model can read ``config.x.y``.

    ``TFC_TDF_net`` expects an OmegaConf/ConfigDict-style object. We load the
    bundled YAML as a plain dict (also consumed as-is by :func:`_demix`) and wrap
    it here, avoiding an extra config dependency.
    """

    def __init__(self, data: dict):
        object.__setattr__(self, "_data", data)

    def __getattr__(self, name: str):
        try:
            value = self._data[name]
        except KeyError as exc:
            raise AttributeError(name) from exc
        return _DotConfig(value) if isinstance(value, dict) else value


def _config_path() -> Path:
    path = _CONFIG_DIR / _CONFIG_NAME
    if not path.exists():
        raise ModelError(f"MDX23C config가 없습니다 / missing bundled config: {path}")
    return path


def _load_config() -> dict:
    import yaml

    # Bundled, trusted file: the plain Loader handles the ``!!python/tuple`` tag
    # the config uses for augmentation params (which SafeLoader rejects).
    with open(_config_path()) as f:
        return yaml.load(f, Loader=yaml.Loader)


def _map_sources(pieces: dict[str, "torch.Tensor"]) -> dict[str, "torch.Tensor"]:
    """Translate raw source names to canonical and order as MDX23C_DRUM_STEMS."""
    logger = get_logger()
    canon: dict[str, "torch.Tensor"] = {}
    for i, (name, tensor) in enumerate(pieces.items()):
        key = _SOURCE_MAP.get(name.strip().lower())
        if key is None:
            # Positional fallback keeps us working if labels ever change.
            key = MDX23C_DRUM_STEMS[i] if i < len(MDX23C_DRUM_STEMS) else name
            logger.debug("MDX23C: unmapped source %r → %s (positional)", name, key)
        canon[key] = tensor
    return {s: canon[s] for s in MDX23C_DRUM_STEMS if s in canon}


class MDX23CSeparator:
    """Adapter exposing the vendored MDX23C drum model through :class:`Separator`."""

    def __init__(self, info: ModelInfo, device: str, *, verbose: bool = False):
        self.info = info
        self._device = device
        self._cfg = _load_config()

        ckpt = download.download_url(
            _CKPT_URL, download.model_cache_dir("mdx23c") / _CKPT_NAME,
            what=f"{info.display} 체크포인트 / checkpoint",
            verbose=verbose, min_bytes=100_000_000,
        )
        self._model = self._build(ckpt, device)

    def _build(self, ckpt_path: Path, device: str):
        import torch

        try:
            from ..vendor.mdx23c import TFC_TDF_net
        except Exception as exc:  # pragma: no cover - import/platform dependent
            raise ModelError(
                f"MDX23C 모델 코드를 불러올 수 없습니다 / could not import model: {exc}"
            ) from exc

        try:
            model = TFC_TDF_net(_DotConfig(self._cfg))
        except Exception as exc:
            raise ModelError(
                f"MDX23C 모델 생성 실패 / failed to build model: {exc}"
            ) from exc

        state = torch.load(ckpt_path, map_location="cpu")
        if isinstance(state, dict) and "state_dict" in state:
            state = state["state_dict"]
        try:
            model.load_state_dict(state)
        except Exception as exc:
            raise ModelError(
                "MDX23C 체크포인트가 모델 구조와 맞지 않습니다(버전 불일치 가능).\n"
                f"  Checkpoint/architecture mismatch: {exc}"
            ) from exc
        model.to(device)
        model.eval()
        return model

    def separate(self, wav: "torch.Tensor", input_sr: int, *,
                 progress: bool = True,
                 progress_cb: ProgressFn | None = None) -> dict[str, "torch.Tensor"]:
        sr = int(self._cfg["audio"]["sample_rate"])
        if input_sr != sr:
            import torchaudio as ta

            get_logger().debug("resampling drums %d -> %d for MDX23C", input_sr, sr)
            wav = ta.functional.resample(wav, input_sr, sr)

        try:
            pieces = _demix(self._cfg, self._model, wav, self._device,
                            progress=progress, desc="mdx23c",
                            progress_cb=progress_cb)
        except (NotImplementedError, RuntimeError) as exc:
            pieces = self._cpu_fallback(wav, exc, progress, progress_cb)
        return {s: t.detach().cpu() for s, t in _map_sources(pieces).items()}

    def _cpu_fallback(self, wav: "torch.Tensor", exc: Exception,
                      progress: bool,
                      progress_cb: ProgressFn | None = None) -> dict[str, "torch.Tensor"]:
        """Retry on CPU once if STFT/complex ops are unsupported on the device
        (e.g. MPS), mirroring LarsNet's fallback."""
        logger = get_logger()
        if self._device == "cpu":
            raise SeparationError(
                f"드럼 세부 분리 실패 / MDX23C separation failed: {exc}"
            ) from exc
        logger.warning(
            "  ! %s 장치에서 드럼 분리에 실패하여 CPU로 대체합니다 / "
            "drum separation failed on %s, falling back to CPU (%s)",
            self._device, self._device, exc,
        )
        self._model.to("cpu")
        self._device = "cpu"
        try:
            return _demix(self._cfg, self._model, wav, "cpu",
                          progress=progress, desc="mdx23c",
                          progress_cb=progress_cb)
        except (NotImplementedError, RuntimeError) as exc2:
            raise SeparationError(
                f"드럼 세부 분리 실패 / MDX23C separation failed (cpu fallback): {exc2}"
            ) from exc2
