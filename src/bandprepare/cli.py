"""Command-line interface for BandPrepare."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .audio import SUPPORTED_FORMATS
from .device import VALID_CHOICES
from .errors import BandPrepareError, EXIT_INTERRUPTED, EXIT_USAGE
from .logging_utils import get_logger, setup_logging
from .pipeline import Options, run
from .separation.stems import STEM_ORDER

ALL_STEMS = set(STEM_ORDER)


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
            "  bandprepare song.mp3 --no-drum-split --device cpu\n"
        ),
    )
    parser.add_argument("input", type=str, help="입력 음원 파일 / input audio file (mp3, wav, flac, m4a, ...)")
    parser.add_argument("-o", "--output", type=str, default=None,
                        help="출력 디렉터리 / output directory (default: ./output/<name>/)")
    parser.add_argument("--stems", type=str, default="all",
                        help="분리할 악기 (콤마 구분, 기본 all) / stems to keep, comma-separated. "
                             f"choices: {','.join(STEM_ORDER)}")
    parser.add_argument("--no-drum-split", action="store_true",
                        help="드럼 세부 분리를 건너뜀 / skip drum-kit separation")
    parser.add_argument("--format", dest="fmt", choices=SUPPORTED_FORMATS, default="wav",
                        help="출력 포맷 / output format (default: wav)")
    parser.add_argument("--device", choices=VALID_CHOICES, default="auto",
                        help="연산 장치 / compute device (default: auto)")
    parser.add_argument("--keep-drums-stem", action="store_true",
                        help="세부 분리 후에도 원본 drums stem 보존 / keep the full drums stem too")
    parser.add_argument("--drum-wiener", type=float, default=1.0, metavar="ALPHA",
                        help="드럼 분리 α-Wiener 지수 / alpha-Wiener exponent for drums (default: 1.0)")
    parser.add_argument("--no-drum-wiener", action="store_true",
                        help="드럼 분리 Wiener 필터 비활성화 / disable Wiener filtering for drums")
    parser.add_argument("--overwrite", action="store_true",
                        help="기존 출력 덮어쓰기 / overwrite existing outputs")
    parser.add_argument("-v", "--verbose", action="store_true", help="상세 로그 / verbose logging")
    parser.add_argument("--version", action="version", version=f"bandprepare {__version__}")
    return parser


def parse_stems(value: str) -> list[str]:
    raw = [s.strip().lower() for s in value.split(",") if s.strip()]
    if not raw:
        raise ValueError("스템 목록이 비어 있습니다 / stems list is empty")
    if "all" in raw:
        return list(STEM_ORDER)
    unknown = [s for s in raw if s not in ALL_STEMS]
    if unknown:
        raise ValueError(
            f"알 수 없는 스템: {', '.join(unknown)} / unknown stems. "
            f"choices: {', '.join(STEM_ORDER)}, all"
        )
    # de-duplicate while preserving canonical order
    return [s for s in STEM_ORDER if s in raw]


def default_output_dir(input_path: str) -> Path:
    return Path("output") / Path(input_path).stem


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(args.verbose)
    logger = get_logger()

    try:
        stems = parse_stems(args.stems)
    except ValueError as exc:
        parser.error(str(exc))  # exits with code 2
        return EXIT_USAGE  # unreachable, for type-checkers

    if args.no_drum_wiener or args.drum_wiener <= 0:
        wiener = None
    else:
        wiener = args.drum_wiener

    output_dir = Path(args.output) if args.output else default_output_dir(args.input)

    opts = Options(
        input_path=Path(args.input),
        output_dir=output_dir,
        stems=stems,
        fmt=args.fmt,
        device_choice=args.device,
        drum_split=not args.no_drum_split,
        keep_drums_stem=args.keep_drums_stem,
        wiener_exponent=wiener,
        overwrite=args.overwrite,
        verbose=args.verbose,
    )

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
