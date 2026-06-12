"""RoFormer instrument-stem backend (BS-RoFormer / Mel-Band RoFormer).

Uses the vendored model definitions (``..vendor.roformer``, pinned to ZFTurbo
v1.0.12) so the architecture matches the pretrained checkpoints we download.
Config YAMLs are bundled with the package (tied to each checkpoint); only the
large ``.ckpt`` is fetched at runtime and cached. The chunked-overlap inference
(``_demix``) is a trimmed port of ZFTurbo's ``demix_track`` and is shared with
the MDX23C drum backend.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..errors import ModelError, SeparationError
from ..logging_utils import get_logger
from . import download
from .base import ModelInfo, ProgressFn

if TYPE_CHECKING:  # pragma: no cover - typing only
    import torch

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "vendor" / "roformer" / "configs"


def _config_path(name: str) -> Path:
    path = _CONFIG_DIR / name
    if not path.exists():
        raise ModelError(f"RoFormer config가 없습니다 / missing bundled config: {path}")
    return path


def _load_config(name: str) -> dict:
    import yaml

    # Bundled, trusted file: the plain Loader handles the ``!!python/tuple`` tags
    # the configs use (which SafeLoader rejects).
    with open(_config_path(name)) as f:
        return yaml.load(f, Loader=yaml.Loader)


def build_model(model_type: str, cfg: dict):
    """Instantiate the vendored RoFormer model from a config dict."""
    kwargs = dict(cfg["model"])
    if model_type == "bs_roformer":
        try:
            from ..vendor.roformer.bs_roformer import BSRoformer
        except Exception as exc:
            raise ModelError(
                "RoFormer 의존성이 없습니다. 설치: pip install 'bandprepare[roformer]'\n"
                f"  (rotary-embedding-torch / beartype 필요) / missing roformer deps: {exc}"
            ) from exc
        return BSRoformer(**kwargs)
    if model_type == "mel_band_roformer":
        try:
            from ..vendor.roformer.mel_band_roformer import MelBandRoformer
        except Exception as exc:
            raise ModelError(
                "RoFormer 의존성이 없습니다. 설치: pip install 'bandprepare[roformer]'\n"
                f"  (rotary-embedding-torch / beartype 필요) / missing roformer deps: {exc}"
            ) from exc
        return MelBandRoformer(**kwargs)
    raise ModelError(f"알 수 없는 RoFormer 타입 / unknown roformer type: {model_type}")


def _getWindowingArray(window_size: int, fade_size: int):
    import torch

    fadein = torch.linspace(0, 1, fade_size)
    fadeout = torch.linspace(1, 0, fade_size)
    window = torch.ones(window_size)
    window[-fade_size:] *= fadeout
    window[:fade_size] *= fadein
    return window


def _demix(cfg: dict, model, mix: "torch.Tensor", device: str,
           progress: bool = True, desc: str = "separating",
           progress_cb: ProgressFn | None = None) -> dict[str, "torch.Tensor"]:
    """Chunked-overlap inference. Port of ZFTurbo ``demix_track``.

    ``mix`` is ``(channels, samples)`` float32 at the model's sample rate.
    Returns ``{instrument: (channels, samples)}``. Shared by the RoFormer stem
    backend and the MDX23C drum backend (``desc`` only labels the progress bar;
    ``progress_cb`` additionally receives the chunk-level fraction in [0, 1]).
    """
    import torch
    import torch.nn.functional as F

    instruments = list(cfg["training"]["instruments"])
    target = cfg["training"].get("target_instrument")
    if target:
        instruments = [target]

    C = int(cfg["audio"]["chunk_size"])
    N = int(cfg["inference"]["num_overlap"])
    batch_size = int(cfg["inference"].get("batch_size", 1))
    fade_size = C // 10
    step = C // N
    border = C - step

    length_init = mix.shape[-1]
    if length_init > 2 * border and border > 0:
        mix = F.pad(mix, (border, border), mode="reflect")

    window = _getWindowingArray(C, fade_size)
    use_amp = bool(cfg["training"].get("use_amp", False)) and device == "cuda"

    with torch.cuda.amp.autocast(enabled=use_amp):
        with torch.inference_mode():
            req_shape = (len(instruments),) + tuple(mix.shape)
            result = torch.zeros(req_shape, dtype=torch.float32)
            counter = torch.zeros(req_shape, dtype=torch.float32)

            i = 0
            batch_data: list = []
            batch_locations: list = []
            total = mix.shape[1]
            pbar = None
            if progress:
                try:
                    from tqdm import tqdm

                    pbar = tqdm(total=total, desc=desc, leave=False)
                except Exception:
                    pbar = None

            while i < total:
                part = mix[:, i:i + C].to(device)
                length = part.shape[-1]
                if length < C:
                    pad_mode = "reflect" if length > C // 2 + 1 else "constant"
                    part = F.pad(part, (0, C - length), mode=pad_mode)
                batch_data.append(part)
                batch_locations.append((i, length))
                i += step

                if len(batch_data) >= batch_size or i >= total:
                    arr = torch.stack(batch_data, dim=0)
                    x = model(arr)

                    win = window.clone()
                    if i - step == 0:          # first chunk: no fade-in
                        win[:fade_size] = 1
                    elif i >= total:           # last chunk: no fade-out
                        win[-fade_size:] = 1

                    for j, (start, length) in enumerate(batch_locations):
                        result[..., start:start + length] += x[j][..., :length].cpu() * win[..., :length]
                        counter[..., start:start + length] += win[..., :length]

                    batch_data = []
                    batch_locations = []

                if pbar is not None:
                    pbar.update(step)
                if progress_cb is not None:
                    progress_cb(min(i / total, 1.0))

            if pbar is not None:
                pbar.close()

            estimated = result / counter
            if length_init > 2 * border and border > 0:
                estimated = estimated[..., border:-border]

    estimated = torch.nan_to_num(estimated, nan=0.0)
    return {name: estimated[idx] for idx, name in enumerate(instruments)}


def _load_state_dict(model, ckpt_path: Path):
    import torch

    state = torch.load(ckpt_path, map_location="cpu")
    if isinstance(state, dict) and "state_dict" in state:
        state = state["state_dict"]
    try:
        model.load_state_dict(state)
    except Exception as exc:
        raise ModelError(
            "RoFormer 체크포인트가 모델 구조와 맞지 않습니다(버전 불일치 가능).\n"
            f"  Checkpoint/architecture mismatch: {exc}"
        ) from exc


class RoformerSeparator:
    """Adapter exposing a vendored RoFormer model through :class:`Separator`."""

    def __init__(self, info: ModelInfo, device: str, *, model_type: str,
                 config_name: str, ckpt_url: str, ckpt_name: str,
                 ckpt_min_bytes: int = 10_000_000, verbose: bool = False):
        self.info = info
        self._device = device
        self._cfg = _load_config(config_name)

        ckpt = download.download_url(
            ckpt_url, download.model_cache_dir("roformer") / ckpt_name,
            what=f"{info.display} 체크포인트 / checkpoint",
            verbose=verbose, min_bytes=ckpt_min_bytes,
        )
        try:
            model = build_model(model_type, self._cfg)
        except ModelError:
            raise
        except Exception as exc:
            raise ModelError(f"RoFormer 모델 생성 실패 / failed to build model: {exc}") from exc
        _load_state_dict(model, ckpt)
        model.to(device)
        model.eval()
        self._model = model

    def separate(self, wav: "torch.Tensor", input_sr: int, *,
                 progress: bool = True,
                 progress_cb: ProgressFn | None = None) -> dict[str, "torch.Tensor"]:
        sr = int(self._cfg["audio"]["sample_rate"])
        if input_sr != sr:
            import torchaudio as ta

            get_logger().debug("resampling %d -> %d for RoFormer", input_sr, sr)
            wav = ta.functional.resample(wav, input_sr, sr)
        try:
            pieces = _demix(self._cfg, self._model, wav, self._device,
                            progress=progress, desc="roformer",
                            progress_cb=progress_cb)
        except (NotImplementedError, RuntimeError) as exc:
            raise SeparationError(
                f"악기 분리 실패 / RoFormer separation failed: {exc}"
            ) from exc
        pieces = self._add_complement(wav, pieces)
        return {name: t.detach().cpu() for name, t in pieces.items()}

    def _add_complement(self, mix: "torch.Tensor", pieces: dict) -> dict:
        """For single-target models (e.g. vocals), derive the complement stem
        (e.g. instrumental ``other``) as ``mix - target``."""
        target = self._cfg["training"].get("target_instrument")
        instruments = list(self._cfg["training"]["instruments"])
        if not (target and len(instruments) == 2 and target in pieces and len(pieces) == 1):
            return pieces
        others = [s for s in instruments if s != target]
        tgt = pieces[target]
        length = min(mix.shape[-1], tgt.shape[-1])
        pieces[others[0]] = mix[..., :length].cpu() - tgt[..., :length].cpu()
        return pieces
