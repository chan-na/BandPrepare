"""Command-line interface for BandPrepare."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .audio import SUPPORTED_FORMATS, prepare_ffmpeg_path
from .device import VALID_CHOICES
from .errors import BandPrepareError, EXIT_INTERRUPTED, EXIT_USAGE
from .logging_utils import get_logger, setup_logging
from .pipeline import Options, run
from .separation import registry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bandprepare",
        description=(
            "음원을 악기별 트랙으로 분리하고 드럼은 킥/스네어/하이햇/심벌/톰으로 세분화합니다.\n"
            "Split a song into per-instrument tracks; further split drums into "
            "kick/snare/hihat/cymbals/toms."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "예시 / examples:\n"
            "  bandprepare song.mp3\n"
            "  bandprepare song.wav -o out/ --format flac\n"
            "  bandprepare song.mp3 --stems vocals,drums,bass\n"
            "  bandprepare song.mp3 --minus bass        # 베이스 뺀 합본 / play-along\n"
            "  bandprepare song.mp3 --stem-model htdemucs_ft --no-drum-split\n"
            "  bandprepare song.mp3 --drum-model drumsep\n"
            "  bandprepare --list-models\n"
        ),
    )
    parser.add_argument("input", type=str, nargs="?", default=None,
                        help="입력 음원 파일 / input audio file (mp3, wav, flac, m4a, ...)")
    parser.add_argument("-o", "--output", type=str, default=None,
                        help="출력 디렉터리 / output directory (default: ./output/<name>/)")
    parser.add_argument("--stem-model", choices=registry.stem_model_ids(),
                        default=registry.DEFAULT_STEM_MODEL,
                        help="악기 분리 모델 / instrument-separation model "
                             f"(default: {registry.DEFAULT_STEM_MODEL}). see --list-models")
    parser.add_argument("--drum-model", choices=registry.drum_model_ids(),
                        default=registry.DEFAULT_DRUM_MODEL,
                        help="드럼 세부 분리 모델 / drum-kit model "
                             f"(default: {registry.DEFAULT_DRUM_MODEL}). see --list-models")
    parser.add_argument("--list-models", action="store_true",
                        help="사용 가능한 모델 목록 출력 후 종료 / list available models and exit")
    parser.add_argument("--stems", type=str, default="all",
                        help="분리할 악기 (콤마 구분, 기본 all) / stems to keep, comma-separated. "
                             "선택지는 --stem-model 에 따라 다름 / choices depend on --stem-model "
                             "(see --list-models)")
    parser.add_argument("--minus", type=str, default=None, metavar="STEM[,STEM...]",
                        help="해당 악기를 뺀 합본(마이너스원) 생성 / mix minus the given stem(s), "
                             "comma-separated (e.g. --minus vocals or --minus vocals,bass)")
    parser.add_argument("--no-drum-split", action="store_true",
                        help="드럼 세부 분리를 건너뜀 / skip drum-kit separation")
    parser.add_argument("--format", dest="fmt", choices=SUPPORTED_FORMATS, default="wav",
                        help="출력 포맷 / output format (default: wav)")
    parser.add_argument("--device", choices=VALID_CHOICES, default="auto",
                        help="연산 장치 / compute device (default: auto)")
    parser.add_argument("--keep-drums-stem", action="store_true",
                        help="세부 분리 후에도 원본 drums stem 보존 / keep the full drums stem too")
    parser.add_argument("--drum-wiener", type=float, default=None, metavar="ALPHA",
                        help="드럼 분리 α-Wiener 지수 (LarsNet 전용, 기본 1.0) / "
                             "alpha-Wiener exponent for drums (LarsNet only, default 1.0)")
    parser.add_argument("--no-drum-wiener", action="store_true",
                        help="드럼 분리 Wiener 필터 비활성화 / disable Wiener filtering for drums")
    parser.add_argument("--overwrite", action="store_true",
                        help="기존 출력 덮어쓰기 / overwrite existing outputs")
    parser.add_argument("-v", "--verbose", action="store_true", help="상세 로그 / verbose logging")
    parser.add_argument("--version", action="version", version=f"bandprepare {__version__}")
    return parser


def parse_stems(value: str, allowed: tuple[str, ...]) -> list[str]:
    """Validate ``--stems`` against the selected model's ``allowed`` stems."""
    allowed_set = set(allowed)
    raw = [s.strip().lower() for s in value.split(",") if s.strip()]
    if not raw:
        raise ValueError("스템 목록이 비어 있습니다 / stems list is empty")
    if "all" in raw:
        return list(allowed)
    unknown = [s for s in raw if s not in allowed_set]
    if unknown:
        raise ValueError(
            f"이 모델에 없는 스템: {', '.join(unknown)} / unknown stems for this model. "
            f"choices: {', '.join(allowed)}, all"
        )
    # de-duplicate while preserving the model's canonical order
    return [s for s in allowed if s in raw]


def default_output_dir(input_path: str) -> Path:
    return Path("output") / Path(input_path).stem


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(args.verbose)
    logger = get_logger()

    if args.list_models:
        print(registry.format_table())
        return 0

    if not args.input:
        parser.error("입력 파일이 필요합니다 / input file is required")
        return EXIT_USAGE  # unreachable, for type-checkers

    stem_info = registry.resolve_stem(args.stem_model)
    try:
        stems = parse_stems(args.stems, stem_info.output_stems)
    except ValueError as exc:
        parser.error(str(exc))  # exits with code 2
        return EXIT_USAGE  # unreachable, for type-checkers

    # --minus is validated against the same model's stems, but independently of
    # --stems: the mix-minus is built from all stage-1 sources regardless of
    # which stems are saved.
    minus: list[str] = []
    if args.minus:
        allowed = set(stem_info.output_stems)
        requested = [s.strip().lower() for s in args.minus.split(",") if s.strip()]
        unknown = [s for s in requested if s not in allowed]
        if unknown:
            parser.error(
                f"--minus: 이 모델에 없는 스템 {', '.join(unknown)} / "
                f"unknown stems for this model. choices: {', '.join(stem_info.output_stems)}"
            )
            return EXIT_USAGE  # unreachable, for type-checkers
        # de-duplicate while preserving the model's canonical order
        minus = [s for s in stem_info.output_stems if s in requested]

    # Wiener filtering is a LarsNet-specific knob; warn (don't fail) if the user
    # set it while a different drum model is selected.
    wiener_explicit = args.no_drum_wiener or args.drum_wiener is not None
    if args.no_drum_wiener or (args.drum_wiener is not None and args.drum_wiener <= 0):
        wiener = None
    elif args.drum_wiener is None:
        wiener = 1.0
    else:
        wiener = args.drum_wiener
    if wiener_explicit and args.drum_model != "larsnet" and not args.no_drum_split:
        logger.warning(
            "  ! --drum-wiener/--no-drum-wiener 는 LarsNet 전용이며 '%s' 에서는 무시됩니다 / "
            "Wiener options apply to LarsNet only; ignored for '%s'.",
            args.drum_model, args.drum_model,
        )

    output_dir = Path(args.output) if args.output else default_output_dir(args.input)

    opts = Options(
        input_path=Path(args.input),
        output_dir=output_dir,
        stems=stems,
        fmt=args.fmt,
        device_choice=args.device,
        stem_model=args.stem_model,
        drum_model=args.drum_model,
        drum_split=not args.no_drum_split,
        keep_drums_stem=args.keep_drums_stem,
        wiener_exponent=wiener,
        overwrite=args.overwrite,
        verbose=args.verbose,
        minus=minus,
    )

    # Make a usable ffmpeg resolvable (bundled or system) before decoding.
    prepare_ffmpeg_path()

    try:
        return run(opts)
    except BandPrepareError as exc:
        logger.error("")
        logger.error("오류 / error: %s", exc.message)
        return exc.exit_code
    except KeyboardInterrupt:
        logger.error("\n중단됨 / interrupted")
        return EXIT_INTERRUPTED


if __name__ == "__main__":
    sys.exit(main())
