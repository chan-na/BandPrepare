# BandPrepare 아키텍처 / Architecture

BandPrepare의 내부 구조와 설계 결정을 정리합니다. (사용법은 [README.md](README.md) 참고)

---

## 1. 개요 / Overview

BandPrepare는 음원 한 곡을 **2단계**로 분리하는 CLI입니다.

```
입력 음원 (mp3/wav/flac/m4a …)
        │
        ▼
┌────────────────────────────────────────────────────────────┐
│ Stage 1 — 악기 분리 (stem)        --stem-model               │
│   htdemucs_6s / htdemucs_ft / bs_roformer / mel_band_roformer│
│   → {vocals, drums, bass, (guitar, piano,) other …}          │
└───────────────┬──────────────────────────────────────────────┘
                │  "drums" 스템
                ▼
┌────────────────────────────────────────────────────────────┐
│ Stage 2 — 드럼 세부 분리 (drum)    --drum-model              │
│   larsnet / drumsep / mdx23c                                 │
│   → {kick, snare, (hihat,) cymbals/(ride,crash,) toms}       │
└───────────────┬──────────────────────────────────────────────┘
                ▼
   output/<곡>/instruments/*.wav,  output/<곡>/drums/*.wav

   (선택) --minus: 원본 믹스 − Σ(선택 스템) → output/<곡>/mixes/minus-*.wav
```

두 단계 모두 **여러 모델 중 선택**할 수 있고, 각 모델은 동일한 `Separator`
인터페이스 뒤에 숨겨진 **어댑터**로 구현됩니다. 선택지·메타데이터는 단일
**레지스트리**(`separation/registry.py`)가 관리합니다.

---

## 2. 모듈 구성 / Module map

```
src/bandprepare/
├── cli.py                  # 인자 파싱, --list-models, 모델별 --stems 검증, 진입점
├── pipeline.py             # 2단계 오케스트레이션 (Options, run, planned_outputs, compute_minus)
├── audio.py                # 입출력 / ffmpeg 점검 (load_track, save_waveform)
├── device.py               # --device 해석 (auto/cpu/cuda/mps, Intel-Mac MPS 회피)
├── errors.py               # 사용자용 에러 타입 + 종료 코드
├── logging_utils.py        # stage/step 로깅 헬퍼
├── separation/
│   ├── base.py             # ★ Separator 프로토콜 + ModelInfo 데이터클래스
│   ├── registry.py         # ★ 모델 카탈로그(STEM_MODELS/DRUM_MODELS) + resolve/loader
│   ├── download.py         # 가중치 다운로드/캐시 공용 헬퍼 (URL/gdrive)
│   ├── stems.py            # Demucs 백엔드 (htdemucs_6s / htdemucs_ft)
│   ├── roformer.py         # RoFormer 백엔드 + 청크 추론 엔진(_demix)
│   ├── drums.py            # LarsNet 백엔드
│   ├── drumsep.py          # DrumSep(inagoy, Hybrid Demucs) 백엔드
│   └── mdx23c.py           # MDX23C(TFC-TDF v3) 드럼 백엔드 (ride/crash까지 분리)
└── vendor/
    ├── larsnet/            # 벤더링한 LarsNet 모델 코드
    ├── roformer/           # 벤더링한 BS/Mel-Band RoFormer (ZFTurbo v1.0.12, MIT)
    │   └── configs/        # 체크포인트에 묶인 모델 config(YAML) 동봉
    └── mdx23c/             # 벤더링한 TFC-TDF v3 (ZFTurbo v1.0.12, MIT)
        └── configs/        # 드럼 6스템 체크포인트 config(YAML) 동봉
```

★ = 모델 선택 기능의 핵심.

---

## 3. 핵심 설계 — 레지스트리 + 어댑터 / Registry + adapter

### 3.1 `Separator` 프로토콜과 `ModelInfo` (`base.py`)

모든 백엔드는 동일한 최소 인터페이스를 따릅니다.

```python
class Separator(Protocol):
    info: ModelInfo
    def separate(self, wav, input_sr, *, progress=True) -> dict[str, Tensor]: ...
        # {stem_name: (channels, samples)}  @ info.samplerate
```

모델의 정적 메타데이터는 불변 데이터클래스로 표현합니다.

```python
@dataclass(frozen=True)
class ModelInfo:
    id: str                       # CLI 값 (예: "bs_roformer")
    kind: str                     # "stem" | "drum"
    display: str                  # 로그/목록 표기
    output_stems: tuple[str, ...] # 이 모델이 내는 스템/조각 (권위 있는 출처)
    samplerate: int
    load: Loader                  # (info, device, **opts) -> Separator
    channels: int = 2
    license_note: str = ""
```

`output_stems`가 **모델별로** 다르다는 점이 설계의 중심입니다(htdemucs_6s만
6스템, RoFormer는 4 또는 2스템). 그래서:

- `cli.parse_stems(value, allowed)` — 선택한 모델의 `output_stems` 기준으로
  `--stems`를 검증(예: `bs_roformer`에 `guitar` 요청 → 거부).
- `pipeline.planned_outputs` — 선택한 드럼 모델의 `output_stems`로 결과 파일 계획.
- `pipeline.run` — 오디오를 `info.samplerate`/`info.channels`로 로딩(모델 인스턴스
  생성 전에 결정 가능).

### 3.2 레지스트리 (`registry.py`)

`STEM_MODELS` / `DRUM_MODELS` 딕셔너리가 카탈로그이며, **로더는 백엔드를 지연
import**합니다. 덕분에 `--list-models`나 CLI choices 구성은 무거운 스택(torch 등)을
불러오지 않습니다.

```python
def _roformer_loader(*, model_type, config_name, ckpt_url, ckpt_name):
    def load(info, device, **kw):
        from .roformer import RoformerSeparator      # ← 지연 import
        return RoformerSeparator(info, device, model_type=model_type, ...)
    return load
```

`resolve_stem(id)` / `resolve_drum(id)`는 미존재 시 가용 목록을 담은
`ModelError`를 던집니다. `format_table()`은 `--list-models` 출력.

### 3.3 모델별 지식(knobs)은 생성자에서

각 단계 공통 호출은 `separate(wav, input_sr, progress=)`로 균일하게 두고,
모델 고유 옵션은 **로더/생성자**로 전달합니다.

- stem: `load(info, device, shifts=…)`  (Demucs만 사용, RoFormer는 무시)
- drum: `load(info, device, wiener_exponent=…, verbose=…)` (LarsNet 전용,
  나머지는 무시 — CLI가 비-LarsNet에서 `--drum-wiener` 사용 시 1회 경고)

---

## 4. 2단계 파이프라인 흐름 / Pipeline flow (`pipeline.py`)

```python
stem_info = registry.resolve_stem(opts.stem_model)
drum_info = registry.resolve_drum(opts.drum_model) if will_split else None

separator = stem_info.load(stem_info, device, shifts=opts.shifts)   # 가중치 로드/다운로드
wav       = audio.load_track(input, stem_info.channels, stem_info.samplerate)
sources   = separator.separate(wav, stem_info.samplerate)           # {name: tensor}
# opts.stems 에 해당하는 스템만 저장. drums는 분리 시 stage 2로.

if opts.minus:                                                       # 마이너스원(play-along)
    mixdown = compute_minus(wav, sources, opts.minus)               # mix − Σ(선택 스템)
    audio.save_waveform(mixdown, …/mixes/minus-….wav, stem_info.samplerate)

if drum_info:
    drum_sep = drum_info.load(drum_info, device, wiener_exponent=…)
    pieces   = drum_sep.separate(sources["drums"], stem_info.samplerate)
    # drum_info.output_stems 순서로 저장 (drum_info.samplerate)
```

- 드럼 세부 분리는 **stem 모델이 `drums`를 내고 사용자가 `drums`를 선택**할 때만
  수행됩니다. `mel_band_roformer`(보컬/반주 2스템)는 `drums`가 없으므로 자동으로
  꺼집니다.
- `--minus` 는 **메모리에 살아 있는 원본 믹스(`wav`)와 전체 `sources`** 로 합본을
  만듭니다. `--stems`(개별 스템 저장)와 독립적이라 저장하지 않은 스템도 뺄 수 있고,
  길이는 `compute_minus` 가 최단 텐서에 맞춰 정합합니다(RoFormer 등 약간의 트리밍 대비).
  드럼 조각(킥/스네어 등) 단위 마이너스는 SR 차이/드럼 분리 선행 문제로 아직 미지원.
- 모든 출력이 이미 존재하면(`planned_outputs`) `--overwrite` 없이는 건너뜁니다.

---

## 5. 가중치 다운로드 & 캐시 / Weights & cache (`download.py`)

캐시 위치는 `BANDPREPARE_CACHE` → `XDG_CACHE_HOME` → `~/.cache` 순으로 결정되며
`<cache>/bandprepare/<모델>/` 아래에 저장됩니다.

| 모델 | 받는 것 | 방식 | 캐시 경로 |
|------|---------|------|-----------|
| Demucs (htdemucs_*) | Demucs 가중치 | demucs 내장 | `~/.cache/torch` |
| LarsNet | 5개 체크포인트(zip, ~562MB) | gdown | `~/.cache/bandprepare/larsnet` |
| DrumSep | `49469ca8.th`(~167MB) | gdown | `~/.cache/bandprepare/drumsep` |
| RoFormer | `.ckpt`(~500–870MB) | urllib(GitHub/HF) | `~/.cache/bandprepare/roformer` |
| MDX23C | `MDX23C-DrumSep-….ckpt`(~438MB) | urllib(HF) | `~/.cache/bandprepare/mdx23c` |

공용 헬퍼: `model_cache_dir(name)`, `download_url(url, dest, …)`,
`download_gdrive(file_id, dest, …)` — 모두 멱등(이미 받았으면 재사용)·부분
다운로드 방지.

---

## 6. 벤더링한 모델 코드 / Vendored models

순수 파이썬 모델 정의는 저장소에 직접 포함합니다.

- **LarsNet** (`vendor/larsnet/`) — 코드 MIT, **사전학습 체크포인트는 CC BY-NC 4.0
  (비상업)**. 상업적 사용 시 주의([docs/REFERENCE.md](docs/REFERENCE.md#모델-출처--라이선스--model-sources--licenses) 라이선스 메모 참고).
- **RoFormer** (`vendor/roformer/`) — `bs_roformer.py`, `mel_band_roformer.py`,
  `attend.py`를 [ZFTurbo/Music-Source-Separation-Training](https://github.com/ZFTurbo/Music-Source-Separation-Training)
  **태그 `v1.0.12`** 에서 복사(내부 import만 상대 경로로 수정). lucidrains 구현
  기반, MIT.

> **왜 태그 고정인가**: 모델 코드와 사전학습 체크포인트의 `state_dict` 키가 맞아야
> 합니다. pip의 `BS-RoFormer` 최신 패키지는 아키텍처가 드리프트(hyper-connections,
> PoPE 등)해 공개 체크포인트 로딩이 깨질 수 있습니다. 그래서 패키지 의존 대신,
> 체크포인트(v1.0.12 릴리스 자산)와 **같은 버전의 모델 코드**를 벤더링합니다.

체크포인트에 묶인 **config(YAML)도 패키지에 동봉**(`vendor/roformer/configs/`)해
런타임엔 대용량 `.ckpt`만 받습니다. config는 신뢰된 동봉 파일이므로
`yaml.load(Loader=yaml.Loader)`로 `!!python/tuple` 태그를 처리합니다.

### Mel-Band가 2스템인 이유

공개 Mel-Band RoFormer 체크포인트는 전부 보컬 분리(2스템: vocals/instrumental) 등
특수 목적이고, 4스템 범용 가중치는 공개돼 있지 않습니다. 그래서 Mel-Band는
**보컬/반주 추출기**(KimberleyJensen, SDR vocals 10.98)로 등록하고, 반주(`other`)는
`mix − vocals`로 계산합니다(`RoformerSeparator._add_complement`). BS-RoFormer는
4스템(vocals/drums/bass/other) 가중치가 있어 그대로 4스템 모델입니다.

---

## 7. 공유 추론 엔진 / Shared inference (`roformer._demix`)

RoFormer는 ZFTurbo `demix_track`을 옮긴 **청크-오버랩 추론**을 씁니다.

- `chunk_size`만큼 잘라 `num_overlap` 간격으로 처리, 경계는 크로스페이드 윈도로
  합성(클릭 잡음 완화).
- 입력은 모델 SR로 리샘플, 출력은 `{instrument: (channels, samples)}`.
- AMP는 CUDA에서만 활성. (벤더 모델은 MPS의 STFT/ISTFT 미지원을 내부에서 CPU로
  폴백 처리.)

이 엔진은 아키텍처에 무관하게 `(B,C,T) → (B,S,C,T)` 모델이면 재사용 가능합니다.
실제로 MDX23C 드럼 백엔드(`mdx23c.py`)가 이 `_demix`를 그대로 재사용합니다(진행바
라벨 `desc`만 모델별로 다름).

---

## 8. 장치 처리 / Devices (`device.py`)

`auto`는 CUDA → (Apple Silicon)MPS → CPU 순으로 선택합니다. **Intel Mac**에서는
MPS가 "사용 가능"으로 보고돼도 이 모델들엔 느리거나 멈춰서, `auto`가 의도적으로
CPU를 고릅니다(`--device mps`로 강제 가능). LarsNet은 MPS 실패 시 CPU로 자동 폴백.

---

## 9. 호환성 — audio-separator를 쓰지 않은 이유 / Why not audio-separator

모델 선택을 가장 쉽게 구현하는 방법은 [`audio-separator`](https://github.com/nomadkaraoke/python-audio-separator)
같은 통합 래퍼를 쓰는 것이지만, **의도적으로 채택하지 않았습니다.**

### 충돌 지점

| | BandPrepare(고정) | audio-separator(요구) |
|---|---|---|
| torch | `>=2.1, <2.3` | **`>=2.3`** |
| numpy | `<2` | **`>=2`** |

`torch<2.3` 핀은 임의가 아니라 **플랫폼 제약**입니다.

- PyTorch는 **2.2.2 이후 Intel(x86_64) macOS 휠을 제공하지 않습니다**(소스 빌드만).
- BandPrepare의 주 개발 머신이 **Intel Mac(x86_64)** 입니다.
- 따라서 `torch>=2.3`으로 올리면 → 이 머신에 prebuilt 휠이 없어 → **프로젝트가
  동작하지 않습니다.** audio-separator는 `torch>=2.3 / numpy>=2`를 요구하므로
  채택 시 곧장 이 회귀가 발생합니다.

### 대신 택한 방식 — 어댑터 패턴

RoFormer·Demucs·DrumSep 등 **아키텍처 자체는 torch 2.2에서 잘 돕니다**(2.3을
*필요로* 하지 않음). 그래서 통합 래퍼 대신 각 모델을 **직접 로딩**합니다.

- Demucs: `demucs` 패키지 그대로.
- RoFormer: 모델 코드 벤더링(§6) + 체크포인트 직접 다운로드 + 자체 추론(§7).
- DrumSep: `demucs`의 커스텀 repo 로딩(`get_model(sig, repo=…)`).

**트레이드오프**: 모델당 약간의 글루 코드가 늘지만, torch 버전을 우리가 통제하고
플랫폼(특히 Intel-Mac) 지원을 잃지 않습니다.

### 같은 결의 추가 핀 — numba/llvmlite

Mel-Band RoFormer가 의존하는 `librosa → numba → llvmlite`도 최신 릴리스가
x86_64 macOS 휠을 끊었습니다(소스 빌드 실패). 그래서 `roformer` extra에서
`numba<0.61`, `llvmlite<0.44`로 상한을 둬 Intel-Mac에서 설치되게 합니다. 이
의존성들은 RoFormer를 쓸 때만 필요하므로 **선택적 extra `.[roformer]`** 로 분리해
기본 설치를 가볍고 안전하게 유지합니다.

### 플랫폼 지원 요약

| OS / 아키텍처 | 상태 |
|---|---|
| macOS Intel (x86_64) | ✅ torch 2.2.2 (주 개발 환경) |
| macOS Apple Silicon | ✅ (MPS 가속) |
| Linux x86_64 / aarch64 | ✅ (CUDA/CPU) |
| Windows x86_64 | ✅ (CUDA/CPU) |

---

## 10. 새 모델 추가하기 / Adding a model

1. 백엔드 작성: `separation/<name>.py`에 `Separator` 프로토콜을 만족하는 클래스
   (`info`, `separate(wav, input_sr, *, progress)`).
2. 가중치 다운로드는 `download.py` 헬퍼 재사용. 큰 가중치만 런타임 다운로드,
   작은 config는 동봉 권장.
3. `registry.py`에 로더(지연 import) + `ModelInfo` 항목 추가
   (`output_stems`/`samplerate`/`license_note` 정확히 기입).
4. 끝 — CLI choices·`--list-models`·`--stems` 검증·파이프라인이 자동 반영됩니다.
5. `tests/test_unit.py`에 레지스트리/스템 검증 테스트 추가, 실제 분리는 샘플로 E2E.

> 예: **MDX23C 6스템 드럼**(`mdx23c`, kick/snare/toms/hihat/ride/crash)이 이 절차로
> 추가됐습니다 — §7 추론 엔진(`_demix`)을 그대로 재사용하고, TFC-TDF v3 모델
> 코드(`vendor/mdx23c/`)와 체크포인트 config만 벤더링했습니다. RoFormer와 달리 base
> 의존성(torch/torchaudio/pyyaml)만으로 동작하므로 `[roformer]` extra가 필요 없습니다.

---

## 11. 테스트 / Testing

- `pytest -q` — 모델 가중치 없이 도는 빠른 단위 테스트(인자 파싱, 모델별 스템
  검증, 레지스트리 해석, 출력 경로 계획, 장치 해석).
- 실제 분리(가중치 다운로드·CPU 추론)는 `tests/make_sample.py`로 만든 합성 클립에
  대해 수동 E2E로 확인합니다([docs/REFERENCE.md](docs/REFERENCE.md#동작-확인-샘플-실행--verified-run) "동작 확인" 참고).

---

## 12. 포터블 배포 & 패키징 / Portable distribution & packaging

비전문가(밴드 멤버)가 ffmpeg·Python·torch를 따로 설치하지 않고 **더블클릭으로
실행**하도록, 플랫폼별 **PyInstaller one-folder** 번들로 배포합니다. 얇은 GUI 층이
CLI와 같은 코어(`pipeline.run`)를 호출하므로 두 진입점이 한 번들을 공유합니다.

### 핵심 결정 / Decision log

| # | 결정 | 사유 |
|---|------|------|
| D1 | 배포 = **PyInstaller one-folder**(플랫폼별) | torch+인터프리터가 네이티브라 단일 범용 바이너리 불가. one-file은 매 실행 ~GB를 temp에 다시 풀어 느림 |
| D2 | Docker / uv-부트스트랩 **탈락** | Docker는 비전문가 GUI에 부적합, uv는 설치 시 deps를 받아 "외부 의존성 다운로드 없음" 원칙 위배 |
| D3 | GUI = **PySide6 (Qt)** | 진짜 네이티브 앱, torch 번들 검증됨 |
| D4 | ffmpeg = **`imageio-ffmpeg` 동봉**(LGPL) | 사용자 `brew install ffmpeg` 제거. 단 ffprobe가 없고 바이너리가 버전 접미사라, 압축 입력은 `audio._decode_with_ffmpeg`(f32le PCM, ffprobe 불필요)로 직접 디코딩(§9 참고) |
| D5 | 모델 가중치는 **런타임 다운로드 유지** | 번들 ~2GB 절감. 캐시는 번들 바깥(`BANDPREPARE_CACHE`→`XDG_CACHE_HOME`→`~/.cache`)이라 frozen 앱에서 쓰기 가능 |
| D6 | RoFormer **동봉**(초기엔 제외 → 해소) | `import librosa`가 numba/llvmlite JIT 스택을 끌어와 동결이 까다로웠음 → Mel-Band의 유일한 librosa 사용(`filters.mel`)을 순수 numpy로 `vendor/roformer/_mel.py`에 벤더링(§6)해 그래프에서 제거. BS·Mel **양쪽 동봉** |
| D7 | **플랫폼별 빌드 필수** | torch가 macOS universal2 휠 미제공, Intel-mac은 torch 2.2.2가 마지막 → mac x86_64 / arm64 / Linux / Win 각각 빌드 |
| D8 | 한 번들에 **CLI + GUI 두 바이너리** | 같은 COLLECT의 라이브러리(torch 등)를 공유 → CLI 추가 비용은 자기 PYZ+부트스트랩뿐 |

### 빌드 & 릴리스

- 스펙: `bandprepare.spec`(onedir, 엔트리=GUI `packaging/bandprepare_gui.py`, CLI는
  같은 COLLECT 위 두 번째 EXE). `collect_all`로 torch/torchaudio/demucs/soundfile/
  imageio_ffmpeg/PySide6, vendor YAML config를 `datas`로 동봉, RoFormer 모델·deps는
  `hiddenimports`(지연 import라 명시).
- CI: `.github/workflows/build.yml`가 4종을 빌드 — linux-x86_64 · macos-arm64 ·
  windows-x86_64는 GitHub-호스티드, **macos-x86_64(Intel)은 self-hosted 러너**(별도
  `build-macos-intel` 잡, 태그/수동 디스패치 게이팅). 각 잡이 **동결 self-test**
  (`BANDPREPARE_GUI_SELFTEST=1`, 오프스크린)로 임포트·동봉 ffmpeg·캐시 쓰기·RoFormer
  인스턴스화를 검증한 뒤, `v*` 태그면 번들을 draft GitHub Release에 첨부.

### 코드서명 / Gatekeeper · SmartScreen (미적용)

코드서명·공증은 **유료 인증서**가 필요해 보류 상태입니다. 미서명이어도 배포·실행은
가능하나 첫 실행 경고가 뜹니다([docs/DEVELOPMENT.md](docs/DEVELOPMENT.md#다운로드한-릴리스-첫-실행-서명-경고-우회) "다운로드한 릴리스 첫 실행" 참고):

- **macOS**: arm64는 PyInstaller가 자동 ad-hoc 서명해 로컬 실행은 되지만, 다운로드
  격리(`com.apple.quarantine`)가 붙으면 차단됩니다. onedir 번들은 `.app`이 아니라 폴더
  안에 수백 개의 `.dylib`/framework가 들어있고 **각각 격리**되어, 메인 실행 후
  `_internal/Python` 등 하위 라이브러리 로드에서 `library load disallowed by system
  policy`로 실패합니다. 시스템 설정의 "확인 없이 열기"는 더블클릭한 **그 파일 하나**의
  격리만 풀어 하위 dylib엔 안 통하므로, **`xattr -dr com.apple.quarantine <받은폴더>`**
  (재귀 `-r`)로 트리 전체 격리를 제거하는 것이 신뢰 가능한 방법입니다.
- **Windows**: SmartScreen "추가 정보 → 실행". 일부 백신이 PyInstaller 바이너리를 오탐.
- **Linux**: 코드서명 개념 없음 — 경고 없이 실행.

### torch 휠: 포터블 번들은 CPU, GPU는 pip 경로 (D9)

초기엔 GPU 가속 유지를 위해 Linux/Windows도 기본 PyPI(CUDA) 휠을 번들했으나, **Linux
CUDA 번들의 `.tar.gz`가 GitHub Release의 자산당 2 GiB 한도를 초과**(raw ~3.5 GB, CUDA
런타임이 ~2 GB)해 릴리스 첨부가 실패했습니다. CUDA는 `libtorch_cuda.so`에 컴파일돼 있어
모델 가중치처럼 런타임에 lazy 다운로드해 붙일 수 없고(frozen 프로세스가 이미 번들 torch를
import한 상태), 번들 자체도 한도를 못 맞춥니다.

→ **포터블 번들은 Linux/Windows 모두 CPU 전용 torch**(`--index-url .../whl/cpu`)로 빌드해
플랫폼당 ~500 MB로 통일합니다(2 GiB 통과, Windows는 기존 기본 휠도 사실상 CPU라 일관). CI의
`Install CPU-only torch (Linux/Windows)` 스텝이 pyproject 핀과 동일 버전으로 선설치하므로
editable 설치가 torch를 건드리지 않습니다. macOS는 CUDA 휠이 없어(MPS/CPU) 기본 그대로.

**GPU(CUDA)는 pip 경로로 제공**: 사용자가 `pip install torch --index-url .../whl/cu121`로
CUDA 빌드를 직접 설치하면 됩니다(필요할 때만 CUDA 런타임 다운로드 — frozen 번들이 아닌 실제
venv라 정상 동작). Linux/Windows + NVIDIA 전용. [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md#gpu-가속-cuda--소스-설치) "GPU 가속 (CUDA)" 참고.

### 동결 번들의 TLS 인증서 (certifi)

PyInstaller가 동봉하는 OpenSSL의 기본 인증서 경로(OPENSSLDIR)는 **빌드 머신**을 가리켜
사용자 머신엔 없습니다. 그대로 두면 모델 가중치 HTTPS 다운로드가 네트워크와 무관하게
`CERTIFICATE_VERIFY_FAILED`로 실패합니다. `certifi`는 이미 번들에 포함되므로
(`_internal/certifi/cacert.pem`), 진입점에서 `_ssl_certs.configure_ssl_cert_file()`이
**동결 시에만** `SSL_CERT_FILE`/`SSL_CERT_DIR`를 그쪽으로 export합니다(사용자 지정값은 존중).
동결 self-test 출력의 `ssl_cert=...`로 CI에서 검증합니다.

### 동결 번들의 중복 프로세스 방지 (tqdm × multiprocessing)

`tqdm`(demucs·LarsNet 진행률, 다운로드 바)은 첫 바 생성 시 **`multiprocessing.RLock`**을
만드는데(`TqdmDefaultWriteLock`), 이게 세마포어를 등록해 `resource_tracker` 프로세스를
띄웁니다. macOS/Windows는 시작 방식이 `spawn`이라 그 프로세스(및 풀 워커)가 **동결 바이너리를
재실행**하고, 동결 진입점은 진짜 파이썬 인터프리터가 아니라 `main()`을 다시 돌려 — **빈 GUI 창이
하나 더** 뜹니다(CLI는 `unrecognized arguments: -B -S -I -c`로 드러남). 멀티프로세스 tqdm을
쓰지 않으므로 `_frozen_mp.configure_multiprocessing()`이 **동결 시** tqdm에 평범한 스레드
락(`threading.RLock`)을 미리 지정 → mp 프리미티브가 안 생겨 spawn 자체가 없어집니다
(`multiprocessing.freeze_support()`도 함께 호출 — Windows 동결 자식용). self-test 출력의
`mp_guard=ok`로 CI에서 검증합니다.
