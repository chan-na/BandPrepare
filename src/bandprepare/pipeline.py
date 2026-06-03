"""Pipeline orchestration: input -> stage 1 (stems) -> stage 2 (drums) -> output."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from . import audio
from .device import resolve_device
from .errors import BandPrepareError
from .logging_utils import get_logger, stage, step
from .separation import drums as drums_stage
from .separation import stems as stems_stage

INSTRUMENT_SUBDIR = "instruments"
DRUMS_SUBDIR = "drums"


@dataclass
class Options:
    input_path: Path
    output_dir: Path
    stems: list[str]
    fmt: str = "wav"
    device_choice: str = "auto"
    drum_split: bool = True
    keep_drums_stem: bool = False
    wiener_exponent: float | None = 1.0
    overwrite: bool = False
    verbose: bool = False
    shifts: int = 1
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
            for piece in drums_stage.DRUM_STEMS:
                files.append(drm / f"{piece}.{ext}")
        else:
            files.append(instr / f"drums.{ext}")
    return files


def run(opts: Options) -> int:
    logger = get_logger()
    started = time.perf_counter()

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
        return 0

    do_split = _will_split_drums(opts)
    total_stages = 2 if do_split else 1

    logger.info("입력 / input      : %s", opts.input_path)
    logger.info("출력 / output     : %s", opts.output_dir)
    logger.info("장치 / device     : %s", opts.resolved_device)
    logger.info("포맷 / format     : %s", opts.fmt)
    logger.info("스템 / stems      : %s", ", ".join(opts.stems))
    logger.info("드럼분리/drum-split: %s", "on" if do_split else "off")

    # ---- Stage 1: instrument stems -------------------------------------
    stage(logger, 1, total_stages, "악기 분리 / Instrument separation (Demucs htdemucs_6s)")
    step(logger, "모델 로딩 / loading model (first run downloads weights)")
    model = stems_stage.load_model(opts.resolved_device)

    step(logger, "오디오 로딩 / loading audio")
    wav = audio.load_track(opts.input_path, model.audio_channels, model.samplerate)
    duration_s = wav.shape[-1] / model.samplerate
    step(logger, f"길이 / duration: {duration_s:.1f}s @ {model.samplerate} Hz")

    step(logger, "분리 중 / separating (this can take a while on CPU)")
    sources = stems_stage.separate(
        model, wav, opts.resolved_device, shifts=opts.shifts, progress=True
    )

    instr_dir = opts.output_dir / INSTRUMENT_SUBDIR
    written: list[Path] = []

    for name, tensor in sources.items():
        if name not in opts.stems:
            continue
        if name == "drums" and do_split and not opts.keep_drums_stem:
            continue  # drums goes to stage 2; keep the full stem only on request
        out_path = instr_dir / f"{name}.{opts.fmt}"
        audio.save_waveform(tensor, out_path, model.samplerate, opts.fmt)
        written.append(out_path)
        step(logger, f"저장 / saved: {out_path}")

    # ---- Stage 2: drum-kit separation ----------------------------------
    if do_split:
        stage(logger, 2, total_stages, "드럼 세부 분리 / Drum-kit separation (LarsNet)")
        drums_tensor = sources["drums"]
        pieces = drums_stage.separate(
            drums_tensor,
            input_sr=model.samplerate,
            device=opts.resolved_device,
            wiener_exponent=opts.wiener_exponent,
            verbose=opts.verbose,
        )
        drums_dir = opts.output_dir / DRUMS_SUBDIR
        for piece in drums_stage.DRUM_STEMS:
            if piece not in pieces:
                continue
            out_path = drums_dir / f"{piece}.{opts.fmt}"
            audio.save_waveform(pieces[piece], out_path, drums_stage.LARSNET_SR, opts.fmt)
            written.append(out_path)
            step(logger, f"저장 / saved: {out_path}")

    elapsed = time.perf_counter() - started
    logger.info("")
    logger.info("완료 / done in %.1fs — %d개 파일 / %d files", elapsed, len(written), len(written))
    for p in written:
        step(logger, str(p))
    return 0
