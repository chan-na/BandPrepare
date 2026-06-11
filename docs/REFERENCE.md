# BandPrepare — 레퍼런스 (Reference)

의존성·옵션·파이프라인·출력 구조·모델 출처/라이선스·한계·성능·종료 코드를 한곳에 모았습니다.
설치와 사용법은 [CLI 가이드](CLI.md), 설계 배경은 [ARCHITECTURE.md](../ARCHITECTURE.md)를 참고하세요.

> Dependencies, options, pipeline, output layout, model sources & licenses,
> limitations, performance and exit codes. For install/usage see the
> [CLI guide](CLI.md); for design rationale see [ARCHITECTURE.md](../ARCHITECTURE.md).

---

## 주요 의존성 한눈에 / Dependencies at a glance

BandPrepare가 의존하는 외부 요소를 한 표로 정리합니다. **직접 설치가 필요한 것은
① 중 Python 뿐**이고, ② Python 패키지는 `pip install -e .` 가 자동 설치,
③ 모델 가중치는 첫 실행 시 자동 다운로드됩니다.

### ① 시스템 / 런타임

| 항목 | 조건 | 설치 | 필수? |
|------|------|------|-------|
| **Python** | `>=3.10` | python.org / `brew` / pyenv 등 | ✅ 필수 |
| **uv** | — | [astral.sh/uv](https://docs.astral.sh/uv/) | 선택 (없으면 표준 `pip`) |

### ② Python 패키지 — base (`pip install -e .` 가 자동 설치)

| 패키지 | 버전 핀 | 역할 |
|--------|---------|------|
| `torch`, `torchaudio` | `>=2.1, <2.3` | 추론 엔진 (핀 사유는 아래 플랫폼 메모) |
| `demucs` | `==4.0.1` | Stage 1 악기 분리 + DrumSep 로딩 |
| `numpy` | `<2` | torch 2.2 ABI 호환 |
| `soundfile` | `>=0.12` | wav/flac 입출력 (libsndfile 번들, 별도 설치 불필요) |
| `imageio-ffmpeg` | `>=0.5` | mp3·m4a 등 압축 음원 디코딩용 ffmpeg |
| `pyyaml` | `>=6.0` | 벤더 모델 config 로딩 |
| `tqdm` | `>=4.65` | 진행 막대 |
| `gdown` | `>=5.1` | Google Drive 가중치 다운로드(LarsNet/DrumSep) |

> **선택 extra** `.[roformer]` — `bs_roformer`/`mel_band_roformer` 사용 시에만 필요:
> `rotary-embedding-torch`, `beartype`, `einops`, `librosa`,
> `numba (>=0.59,<0.61)`, `llvmlite (>=0.42,<0.44)`.
> **GUI extra** `.[gui]` — 데스크톱 GUI(`bandprepare-gui`)용 `PySide6 (>=6.5)`.
> **build extra** `.[build]` — 포터블 번들 빌드용 `pyinstaller (>=6.0)`.
> **dev extra** `.[dev]` — `pytest (>=7)` (테스트용).

### ③ 모델 가중치 — 첫 실행 시 자동 다운로드 (캐시)

캐시 위치: `BANDPREPARE_CACHE` → `XDG_CACHE_HOME` → `~/.cache` 순으로 결정.

| 모델 | 단계 | 용량 | 받는 곳 | 캐시 경로 |
|------|------|------|---------|-----------|
| Demucs (`htdemucs_*`) | 1 | ~300 MB | PyTorch hub | `~/.cache/torch` |
| LarsNet (기본 드럼) | 2 | ~562 MB | Google Drive (gdown) | `~/.cache/bandprepare/larsnet` |
| DrumSep | 2 | ~167 MB | Google Drive (gdown) | `~/.cache/bandprepare/drumsep` |
| RoFormer | 1 | ~500–870 MB | GitHub / HuggingFace | `~/.cache/bandprepare/roformer` |
| MDX23C | 2 | ~438 MB | HuggingFace | `~/.cache/bandprepare/mdx23c` |

> 💾 **디스크 공간**: 기본 조합(`htdemucs_6s` + `larsnet`)은 약 **860 MB**, 모든 모델을
> 받으면 합계 약 **2 GB** 정도가 캐시에 쌓입니다.
> 🌐 **네트워크**: 첫 실행에는 인터넷 연결이 필요합니다. LarsNet/DrumSep은
> **Google Drive**에서 받으므로, Google Drive 접근이 막힌 환경(사내망 등)에서는
> 실패할 수 있습니다(이때는 `--drum-model mdx23c`처럼 HuggingFace 기반 모델 사용).

> 📌 `torch<2.3`·`numpy<2`·`numba/llvmlite` 등 버전 핀의 배경은 아래 "출력 구조" 절의
> 플랫폼 메모와 [ARCHITECTURE.md](../ARCHITECTURE.md) §9를 참고하세요.

## 옵션 전체 / All options

```
bandprepare <input_audio> [options]

  -o, --output DIR              출력 디렉터리 (기본: ./output/<입력파일명>/)
  --stem-model NAME             악기 분리 모델 (기본: htdemucs_6s). --list-models 참고
  --drum-model NAME             드럼 세부 분리 모델 (기본: larsnet). --list-models 참고
  --list-models                 사용 가능한 모델 목록 출력 후 종료
  --stems LIST                  분리할 악기 선택 (기본: all, 선택지는 모델별로 다름)
  --minus STEM[,STEM...]        해당 악기를 뺀 합본(마이너스원) 생성 → mixes/minus-*.<fmt>
  --no-drum-split               드럼 세부 분리 단계를 건너뜀
  --format {wav,mp3,flac}       출력 포맷 (기본: wav)
  --device {auto,cpu,cuda,mps}  연산 장치 (기본: auto)
  --keep-drums-stem             세부 분리 후에도 원본 drums stem 보존
  --drum-wiener ALPHA           드럼 α-Wiener 지수 (기본: 1.0, 크로스토크 감소)
  --no-drum-wiener              드럼 Wiener 필터 비활성화 (더 빠름)
  --overwrite                   기존 출력 덮어쓰기
  -v, --verbose                 상세 로그
  --version
```

각 옵션의 사용 예시와 연습 목적별 레시피는 [CLI 가이드](CLI.md)를 참고하세요.

## 처리 파이프라인 / Pipeline

두 단계 모두 모델을 선택할 수 있습니다(`--stem-model`/`--drum-model`, `--list-models`).
기본값:

| 단계 | 기본 모델 | 출력 |
|------|------|------|
| **1. 악기 분리** | [Demucs `htdemucs_6s`](https://github.com/facebookresearch/demucs) | `vocals`, `drums`, `bass`, `guitar`, `piano`, `other` |
| **2. 드럼 세부 분리** | [LarsNet](https://github.com/polimi-ispl/larsnet) | `kick`, `snare`, `hihat`, `cymbals`(크래쉬+라이드), `toms` |

선택 가능한 모델 전체는 [CLI 가이드의 "분리 모델 바꾸기"](CLI.md#-분리-모델-바꾸기-모델-선택) 표를 참고하세요
(1단계: `htdemucs_6s`/`htdemucs_ft`/`bs_roformer`/`mel_band_roformer`,
2단계: `larsnet`/`drumsep`/`mdx23c`).

- 1단계 Demucs 가중치는 첫 실행 시 자동 다운로드(`~/.cache/torch`).
- 그 외 모델 체크포인트(LarsNet ~562 MB, RoFormer ~500–870 MB, DrumSep ~167 MB,
  MDX23C ~438 MB)는 첫 실행 시 자동 다운로드 → `~/.cache/bandprepare/<모델>` 에 캐시.

## 출력 구조 / Output layout

```
output/<곡이름>/
├── instruments/
│   ├── vocals.wav  bass.wav  guitar.wav  piano.wav  other.wav
│   └── drums.wav            # --keep-drums-stem 또는 --no-drum-split 시
├── drums/
│   └── kick.wav  snare.wav  hihat.wav  cymbals.wav(크래쉬+라이드)  toms.wav
└── mixes/                     # --minus 사용 시에만
    └── minus-<악기>.wav        # 예: minus-bass.wav, minus-vocals-bass.wav
```

`--stems` 로 일부만 선택하면 해당 파일만 생성됩니다. `drums` 를 선택하지 않으면
드럼 세부 분리도 수행하지 않습니다. `--minus` 는 이와 독립으로 동작해
`mixes/` 에 마이너스원 합본을 추가로 만듭니다(`원본 믹스 − 선택 스템`).

> **플랫폼 메모**: `torch`/`torchaudio`는 `<2.3`으로 고정. Intel(x86_64) macOS용
> PyTorch 휠은 2.2.2가 마지막이기 때문입니다. Linux·Apple Silicon에서도 정상 설치됩니다.
> RoFormer extra(`.[roformer]`)의 `numba`/`llvmlite`도 같은 이유로 상한을 둡니다
> (최신 릴리스는 x86_64 macOS 휠을 제공하지 않음).

## 동작 확인 (샘플 실행) / Verified run

저장소에는 짧은 합성 샘플 생성기가 포함돼 있습니다(실제 음악이 아니라 베이스+드럼+멜로디를
합성한 6초 클립으로, 파이프라인 동작 확인용):

```bash
python tests/make_sample.py -o assets/sample.wav
bandprepare assets/sample.wav -o output/sample
```

실제 Intel macOS(CPU)에서 6초 클립 전체 파이프라인 — 가중치 캐시 후 약 **11초**, 파일 10개.
분리가 실제로 동작함을 보여주는 증거(드럼 5종의 스펙트럼 중심 주파수):

| 트랙 | 스펙트럼 중심 | 해석 |
|------|---------------|------|
| `kick`    |   ~383 Hz | 저역 → 킥 ✔ |
| `toms`    | ~1340 Hz | 중역 → 톰 ✔ |
| `hihat`   | ~10 kHz  | 고역 → 하이햇 ✔ |
| `snare`   | ~10 kHz  | 고역 노이즈 → 스네어 ✔ |
| `cymbals` | (무음)   | 합성 클립에 심벌 없음 → 거의 0 ✔ |

> 합성 클립이라 분리 품질 자체 평가는 어렵지만, 에너지가 올바른 트랙으로 가는 것은
> 확인됩니다. 실제 품질은 실제 음악 파일로 확인하세요.

## 모델 출처 / 라이선스 · Model sources & licenses

- **Demucs** (`htdemucs_6s`) — Meta, MIT License.
  <https://github.com/facebookresearch/demucs>
- **LarsNet** — A. I. Mezza, R. Giampiccolo, A. Bernardini, A. Sarti,
  *"Toward Deep Drum Source Separation"*, Pattern Recognition Letters (2024).
  코드 일부(`src/bandprepare/vendor/larsnet/`)를 벤더링했으며, 사전학습 **체크포인트는
  CC BY-NC 4.0**(비상업)입니다. <https://github.com/polimi-ispl/larsnet>

> ⚠️ LarsNet 체크포인트가 CC BY-NC(비상업) 라이선스이므로, 그 가중치를 사용하는
> 드럼 세부 분리 결과물의 **상업적 이용은 제한**됩니다. 상업적 용도라면 `--no-drum-split`
> 로 1단계 결과(Demucs, MIT)만 사용하세요.

### 모델 선택지 / Model choices

요구 분류(킥/스네어/하이햇/크래쉬/톰)에 가장 잘 맞는 **LarsNet**(5 stem,
하이햇 별도)을 드럼 기본값으로 둡니다. 다만 LarsNet 체크포인트는 비상업 라이선스라,
상업 가능한 [DrumSep](https://github.com/inagoy/drumsep)(Hybrid Demucs, 4 stem,
하이햇 미분리)도 `--drum-model drumsep` 로 선택할 수 있습니다. 라이드·크래시까지
나누고 싶다면 상업 가능한 **MDX23C DrumSep**(6 stem: kick/snare/toms/hihat/ride/crash,
aufr33 & jarredou, MIT)을 `--drum-model mdx23c` 로 쓸 수 있습니다 —
[ZFTurbo MSS-Training](https://github.com/ZFTurbo/Music-Source-Separation-Training)의
TFC-TDF v3 모델 코드를 벤더링했습니다.

악기 분리는 기본 **Demucs `htdemucs_6s`**(6스템, 기타·피아노 포함) 외에
`htdemucs_ft`(4스템 고품질), **RoFormer** 계열(`bs_roformer` 4스템,
`mel_band_roformer` 보컬/반주 2스템 — [ZFTurbo MSS-Training](https://github.com/ZFTurbo/Music-Source-Separation-Training)
의 모델 코드를 벤더링)을 선택할 수 있습니다.

## 알려진 한계 / Known limitations

- **크래쉬 단독 분리 불가**: 공개 모델은 크래쉬를 단독으로 내보내지 않습니다. 크래쉬와
  라이드를 묶어 `cymbals.wav` 로 출력합니다.
- **분리 누설(bleed)**: 완벽 분리가 아니며 트랙 간 약간의 누설이 있습니다. 드럼 단계는
  α-Wiener 필터(`--drum-wiener`, 기본 on)로 누설을 줄입니다.
- **CPU 속도**: GPU가 없으면 곡 길이에 비례해 오래 걸립니다(성능 메모 참고).
- **MPS(Apple/Metal)**:
  - Apple Silicon에서는 `auto`가 MPS를 선택합니다. **Intel Mac**(AMD GPU)에서는 MPS가
    "사용 가능"으로 보고되지만 이 모델들에선 CPU보다 느리거나 멈추는 경우가 많아, `auto`는
    Intel Mac에서 의도적으로 CPU를 선택합니다(`--device mps`로 강제 가능).
  - LarsNet의 일부 복소수 STFT 연산이 MPS에서 미지원일 수 있어, 드럼 단계는 MPS 실행
    실패 시 자동으로 CPU로 폴백합니다.
- **상업적 이용 제한**: 위 라이선스 메모 참고.

## 성능 메모 / Performance notes

관측치: 6초 클립 전체 파이프라인이 Intel macOS **CPU**에서 약 11초(1단계 ~7–8초 +
2단계 ~3초, 가중치 캐시 후). 대략적인 환산(`shifts=1` 기본):

| 장치 | 1단계(Demucs) | 2단계(LarsNet) | 메모리 |
|------|---------------|----------------|--------|
| CPU | 곡 길이의 1–2배 정도 | 수~수십 초 | ~2–4 GB RAM |
| CUDA GPU | 수 초~수십 초 | 수 초 | ~2–4 GB VRAM |

- 첫 실행에는 모델 다운로드 시간이 추가됩니다(Demucs 약 300 MB + LarsNet 562 MB).
- 더 빠르게: `--no-drum-wiener`(드럼 가속) 또는 `--no-drum-split`(2단계 생략).

## 오류 처리 / Exit codes

| 코드 | 의미 |
|------|------|
| 0 | 성공 |
| 2 | 잘못된 사용법/인자 |
| 3 | 입력 파일 문제(없음/디코딩 불가) |
| 4 | 의존성 문제(ffmpeg 미설치, 장치 불가) |
| 5 | 모델 다운로드/로드 실패 |
| 6 | 분리 단계 실패 |
| 130 | 사용자 중단(Ctrl-C) |

---

> 🖥 사용법 → [CLI 가이드](CLI.md) · 🖱 GUI → [GUI 가이드](GUI.md) · 🏗 설계 → [ARCHITECTURE.md](../ARCHITECTURE.md)
