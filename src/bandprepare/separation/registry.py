"""Catalog of selectable separation models.

This module is the single source of truth for which models exist, what they
output, and how to load them. Loaders import their (heavy) backend lazily, so
importing the registry — e.g. to build CLI ``choices`` or print
``--list-models`` — stays cheap.
"""

from __future__ import annotations

from ..errors import ModelError
from .base import ModelInfo
from .drums import DRUM_STEMS, LARSNET_SR
from .drumsep import DRUMSEP_SR, DRUMSEP_STEMS
from .mdx23c import MDX23C_DRUM_STEMS, MDX23C_SR
from .stems import STEM_ORDER, STEM_ORDER_4

DEFAULT_STEM_MODEL = "htdemucs_ft"
DEFAULT_DRUM_MODEL = "mdx23c"


# --- loaders (lazy backend imports) ---------------------------------------

def _demucs_loader(model_name: str):
    def load(info: ModelInfo, device: str, **kw):
        from .stems import DemucsSeparator

        return DemucsSeparator(
            info, device, model_name,
            shifts=kw.get("shifts", 1),
            overlap=kw.get("overlap", 0.25),
        )

    return load


def _larsnet_loader():
    def load(info: ModelInfo, device: str, **kw):
        from .drums import LarsNetSeparator

        return LarsNetSeparator(
            info, device,
            wiener_exponent=kw.get("wiener_exponent", 1.0),
            verbose=kw.get("verbose", False),
        )

    return load


def _drumsep_loader():
    def load(info: ModelInfo, device: str, **kw):
        from .drumsep import DrumSepSeparator

        return DrumSepSeparator(info, device, verbose=kw.get("verbose", False))

    return load


def _mdx23c_loader():
    def load(info: ModelInfo, device: str, **kw):
        from .mdx23c import MDX23CSeparator

        return MDX23CSeparator(info, device, verbose=kw.get("verbose", False))

    return load


def _roformer_loader(*, model_type: str, config_name: str, ckpt_url: str, ckpt_name: str):
    def load(info: ModelInfo, device: str, **kw):
        from .roformer import RoformerSeparator

        return RoformerSeparator(
            info, device,
            model_type=model_type, config_name=config_name,
            ckpt_url=ckpt_url, ckpt_name=ckpt_name,
            verbose=kw.get("verbose", False),
        )

    return load


_ZF_REL = "https://github.com/ZFTurbo/Music-Source-Separation-Training/releases/download"


# --- catalog ---------------------------------------------------------------

STEM_MODELS: dict[str, ModelInfo] = {
    "htdemucs_6s": ModelInfo(
        id="htdemucs_6s",
        kind="stem",
        display="Demucs htdemucs_6s",
        output_stems=STEM_ORDER,
        samplerate=44100,
        load=_demucs_loader("htdemucs_6s"),
        license_note="MIT",
    ),
    "htdemucs_ft": ModelInfo(
        id="htdemucs_ft",
        kind="stem",
        display="Demucs htdemucs_ft (fine-tuned, 4 stems)",
        output_stems=STEM_ORDER_4,
        samplerate=44100,
        load=_demucs_loader("htdemucs_ft"),
        license_note="MIT",
    ),
    "bs_roformer": ModelInfo(
        id="bs_roformer",
        kind="stem",
        display="BS-RoFormer (SDR 9.66, 4 stems)",
        output_stems=STEM_ORDER_4,
        samplerate=44100,
        load=_roformer_loader(
            model_type="bs_roformer",
            config_name="bs_roformer_4stem.yaml",
            ckpt_url=f"{_ZF_REL}/v1.0.12/model_bs_roformer_ep_17_sdr_9.6568.ckpt",
            ckpt_name="model_bs_roformer_ep_17_sdr_9.6568.ckpt",
        ),
        license_note="MIT (code) · 가중치 ZFTurbo MIT / weights MIT",
    ),
    "mel_band_roformer": ModelInfo(
        id="mel_band_roformer",
        kind="stem",
        display="Mel-Band RoFormer (vocals/instrumental, SDR vocals 10.98)",
        output_stems=("vocals", "other"),
        samplerate=44100,
        load=_roformer_loader(
            model_type="mel_band_roformer",
            config_name="mel_band_vocals_kj.yaml",
            ckpt_url="https://huggingface.co/KimberleyJSN/melbandroformer/resolve/main/MelBandRoformer.ckpt",
            ckpt_name="mel_band_roformer_kj.ckpt",
        ),
        license_note="MIT (code) · KimberleyJensen 보컬 2스템 / 2-stem vocal model",
    ),
}

DRUM_MODELS: dict[str, ModelInfo] = {
    "larsnet": ModelInfo(
        id="larsnet",
        kind="drum",
        display="LarsNet (5 pieces, +hihat)",
        output_stems=DRUM_STEMS,
        samplerate=LARSNET_SR,
        load=_larsnet_loader(),
        license_note="CC BY-NC 4.0 (비상업용 / non-commercial)",
    ),
    "drumsep": ModelInfo(
        id="drumsep",
        kind="drum",
        display="DrumSep (inagoy, Hybrid Demucs, 4 pieces)",
        output_stems=DRUMSEP_STEMS,
        samplerate=DRUMSEP_SR,
        load=_drumsep_loader(),
        license_note="MIT (code) · 모델은 저자 논문 기반 / research model",
    ),
    "mdx23c": ModelInfo(
        id="mdx23c",
        kind="drum",
        display="MDX23C DrumSep (aufr33/jarredou, 6 pieces, +ride/crash)",
        output_stems=MDX23C_DRUM_STEMS,
        samplerate=MDX23C_SR,
        load=_mdx23c_loader(),
        license_note="MIT (code) · 체크포인트 aufr33 & jarredou / model weights by aufr33 & jarredou",
    ),
}


# --- lookup / presentation -------------------------------------------------

def stem_model_ids() -> list[str]:
    return list(STEM_MODELS)


def drum_model_ids() -> list[str]:
    return list(DRUM_MODELS)


def resolve_stem(model_id: str) -> ModelInfo:
    try:
        return STEM_MODELS[model_id]
    except KeyError:
        raise ModelError(
            f"알 수 없는 stem 모델 '{model_id}'. 사용 가능: {', '.join(STEM_MODELS)} / "
            f"Unknown stem model '{model_id}'. Available: {', '.join(STEM_MODELS)}"
        ) from None


def resolve_drum(model_id: str) -> ModelInfo:
    try:
        return DRUM_MODELS[model_id]
    except KeyError:
        raise ModelError(
            f"알 수 없는 drum 모델 '{model_id}'. 사용 가능: {', '.join(DRUM_MODELS)} / "
            f"Unknown drum model '{model_id}'. Available: {', '.join(DRUM_MODELS)}"
        ) from None


def format_table() -> str:
    """Human-readable listing for ``--list-models``."""
    lines: list[str] = []

    def section(title: str, models: dict[str, ModelInfo]) -> None:
        lines.append(title)
        for info in models.values():
            stems = ", ".join(info.output_stems)
            lines.append(f"  {info.id:<18} {len(info.output_stems)} stems @ {info.samplerate} Hz")
            lines.append(f"  {'':<18} stems: {stems}")
            if info.license_note:
                lines.append(f"  {'':<18} license: {info.license_note}")
        lines.append("")

    section("악기 분리 / instrument-stem models (--stem-model):", STEM_MODELS)
    section("드럼 세부 분리 / drum-kit models (--drum-model):", DRUM_MODELS)
    return "\n".join(lines).rstrip()
