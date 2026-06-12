"""Pipeline orchestration: input -> stage 1 (stems) -> stage 2 (drums) -> output."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

from . import audio
from .device import resolve_device
from .logging_utils import get_logger, stage, step
from .separation import registry

if TYPE_CHECKING:
    import torch

INSTRUMENT_SUBDIR = "instruments"
DRUMS_SUBDIR = "drums"
MIXES_SUBDIR = "mixes"

# Progress hook: ``callback(stage, fraction, msg)``.
#   stage    — stable machine key (see the emit() calls in run()), so a UI can
#              react without parsing the human text.
#   fraction — coarse overall progress in [0, 1], or None when unknown. Model-
#              internal progress is out of scope (MVP); these are stage-boundary
#              estimates, enough to drive a progress bar / spinner.
#   msg      — bilingual human string for a log panel.
ProgressCallback = Callable[[str, Optional[float], str], None]


def _minus_filename(names: list[str], ext: str) -> str:
    """File name for a mix-minus output, e.g. ``minus-vocals-bass.wav``."""
    return f"minus-{'-'.join(names)}.{ext}"


def compute_minus(
    mix: torch.Tensor, sources: dict[str, torch.Tensor], names: list[str]
) -> torch.Tensor:
    """Return ``mix − Σ sources[name]`` — the full mix with ``names`` removed.

    All tensors must share sample-rate and channel count, which holds for stage-1
    stems (they come back at the mix's SR/channels). Lengths are reconciled to the
    shortest tensor because some backends (e.g. RoFormer) trim a few samples.
    """
    lengths = [mix.shape[-1]] + [sources[n].shape[-1] for n in names]
    length = min(lengths)
    out = mix[..., :length].clone()
    for n in names:
        out = out - sources[n][..., :length]
    return out


@dataclass
class Options:
    input_path: Path
    output_dir: Path
    stems: list[str]
    fmt: str = "wav"
    device_choice: str = "auto"
    stem_model: str = registry.DEFAULT_STEM_MODEL
    drum_model: str = registry.DEFAULT_DRUM_MODEL
    drum_split: bool = True
    keep_drums_stem: bool = True
    wiener_exponent: float | None = 1.0
    overwrite: bool = False
    verbose: bool = False
    shifts: int = 1
    minus: list[str] = field(default_factory=list)
    # Optional UI progress hook. The CLI leaves this None (keeps its tqdm output,
    # so there is no behavioural change); the GUI passes a callback to drive its
    # progress bar + log panel. See ProgressCallback above for the contract.
    progress_callback: Optional[ProgressCallback] = None
    # Filled in during run():
    resolved_device: str = field(default="", init=False)


def _will_split_drums(opts: Options) -> bool:
    return opts.drum_split and "drums" in opts.stems


def planned_outputs(opts: Options) -> list[Path]:
    """All files the run is expected to produce (used for re-run skip logic)."""
    instr = opts.output_dir / INSTRUMENT_SUBDIR
    drm = opts.output_dir / DRUMS_SUBDIR
    ext = opts.fmt
    files: list[Path] = []

    for s in opts.stems:
        if s == "drums":
            continue
        files.append(instr / f"{s}.{ext}")

    if "drums" in opts.stems:
        if _will_split_drums(opts):
            if opts.keep_drums_stem:
                files.append(instr / f"drums.{ext}")
            for piece in registry.resolve_drum(opts.drum_model).output_stems:
                files.append(drm / f"{piece}.{ext}")
        else:
            files.append(instr / f"drums.{ext}")

    if opts.minus:
        files.append(opts.output_dir / MIXES_SUBDIR / _minus_filename(opts.minus, ext))
    return files


def run(opts: Options) -> int:
    logger = get_logger()
    started = time.perf_counter()

    def emit(stage_key: str, fraction: float | None, msg: str) -> None:
        if opts.progress_callback is not None:
            opts.progress_callback(stage_key, fraction, msg)

    stem_info = registry.resolve_stem(opts.stem_model)
    drum_info = registry.resolve_drum(opts.drum_model) if _will_split_drums(opts) else None

    opts.input_path = audio.validate_input(opts.input_path)

    # ffmpeg is only required to decode compressed inputs; wav/flac go through
    # torchaudio directly.
    if opts.input_path.suffix.lower() not in (".wav", ".flac"):
        audio.ensure_ffmpeg()

    opts.resolved_device = resolve_device(opts.device_choice)

    expected = planned_outputs(opts)
    if expected and not opts.overwrite and all(p.exists() for p in expected):
        logger.info(
            "이미 모든 출력이 존재합니다. --overwrite 로 다시 생성하세요. / "
            "All outputs already exist; pass --overwrite to regenerate."
        )
        for p in expected:
            step(logger, str(p))
        emit("done", 1.0, "이미 모든 출력이 존재 / outputs already exist")
        return 0

    do_split = drum_info is not None
    total_stages = 2 if do_split else 1
    emit("start", 0.0, "시작 / starting")

    logger.info("입력 / input      : %s", opts.input_path)
    logger.info("출력 / output     : %s", opts.output_dir)
    logger.info("장치 / device     : %s", opts.resolved_device)
    logger.info("포맷 / format     : %s", opts.fmt)
    logger.info("스템 / stems      : %s", ", ".join(opts.stems))
    if opts.minus:
        logger.info("마이너스 / minus  : %s", ", ".join(opts.minus))
    logger.info("악기모델/stem-model: %s", stem_info.display)
    logger.info("드럼분리/drum-split: %s", "on" if do_split else "off")
    if do_split:
        logger.info("드럼모델/drum-model: %s", drum_info.display)

    # Coarse stage-boundary fractions; the stem stage dominates when there is no
    # drum split, otherwise it shares the bar with the drum stage.
    stems_done_frac = 0.55 if do_split else 0.85

    # ---- Stage 1: instrument stems -------------------------------------
    stage(logger, 1, total_stages, f"악기 분리 / Instrument separation ({stem_info.display})")
    step(logger, "모델 로딩 / loading model (first run downloads weights)")
    emit("stem_model", 0.02, f"악기 모델 로딩 / loading instrument model ({stem_info.display})")
    separator = stem_info.load(stem_info, opts.resolved_device, shifts=opts.shifts)

    step(logger, "오디오 로딩 / loading audio")
    emit("load_audio", 0.05, "오디오 로딩 / loading audio")
    wav = audio.load_track(opts.input_path, stem_info.channels, stem_info.samplerate)
    duration_s = wav.shape[-1] / stem_info.samplerate
    step(logger, f"길이 / duration: {duration_s:.1f}s @ {stem_info.samplerate} Hz")

    step(logger, "분리 중 / separating (this can take a while on CPU)")
    emit("separate_stems", 0.10, "악기 분리 중 / separating instruments")
    sources = separator.separate(wav, stem_info.samplerate, progress=True)

    instr_dir = opts.output_dir / INSTRUMENT_SUBDIR
    written: list[Path] = []

    for name, tensor in sources.items():
        if name not in opts.stems:
            continue
        if name == "drums" and do_split and not opts.keep_drums_stem:
            continue  # drums goes to stage 2; keep the full stem only on request
        out_path = instr_dir / f"{name}.{opts.fmt}"
        audio.save_waveform(tensor, out_path, stem_info.samplerate, opts.fmt)
        written.append(out_path)
        step(logger, f"저장 / saved: {out_path}")
        emit("save", None, f"저장 / saved: {out_path}")

    emit("stems_done", stems_done_frac, "악기 분리 완료 / instruments separated")

    # ---- Mix-minus (play-along) ----------------------------------------
    # mix − Σ(selected stems): the standard karaoke/minus-one recipe. Built from
    # the in-memory mix + all stage-1 sources, so it works for any stem even when
    # that stem was not selected via --stems.
    if opts.minus:
        if set(opts.minus) >= set(stem_info.output_stems):
            logger.warning(
                "  ! --minus 가 모든 스템을 제거합니다 — 결과가 거의 무음일 수 있습니다 / "
                "--minus removes every stem; the result may be near-silent."
            )
        emit("minus", stems_done_frac, "마이너스원 생성 / building mix-minus")
        mixdown = compute_minus(wav, sources, opts.minus)
        out_path = opts.output_dir / MIXES_SUBDIR / _minus_filename(opts.minus, opts.fmt)
        audio.save_waveform(mixdown, out_path, stem_info.samplerate, opts.fmt)
        written.append(out_path)
        step(logger, f"마이너스원 저장 / saved mix-minus: {out_path}")
        emit("save", None, f"마이너스원 저장 / saved mix-minus: {out_path}")

    # ---- Stage 2: drum-kit separation ----------------------------------
    if do_split:
        stage(logger, 2, total_stages, f"드럼 세부 분리 / Drum-kit separation ({drum_info.display})")
        emit("drum_model", 0.62, f"드럼 모델 로딩 / loading drum model ({drum_info.display})")
        drum_separator = drum_info.load(
            drum_info, opts.resolved_device,
            wiener_exponent=opts.wiener_exponent, verbose=opts.verbose,
        )
        emit("separate_drums", 0.68, "드럼 분리 중 / separating drum kit")
        pieces = drum_separator.separate(sources["drums"], stem_info.samplerate, progress=True)
        drums_dir = opts.output_dir / DRUMS_SUBDIR
        for piece in drum_info.output_stems:
            if piece not in pieces:
                continue
            out_path = drums_dir / f"{piece}.{opts.fmt}"
            audio.save_waveform(pieces[piece], out_path, drum_info.samplerate, opts.fmt)
            written.append(out_path)
            step(logger, f"저장 / saved: {out_path}")
            emit("save", None, f"저장 / saved: {out_path}")
        emit("drums_done", 0.98, "드럼 분리 완료 / drum kit separated")

    elapsed = time.perf_counter() - started
    logger.info("")
    logger.info("완료 / done in %.1fs — %d개 파일 / %d files", elapsed, len(written), len(written))
    for p in written:
        step(logger, str(p))
    emit("done", 1.0, f"완료 / done — {len(written)}개 파일 / {len(written)} files")
    return 0
