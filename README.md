# BandPrepare 🥁🎸

음원 한 곡을 **악기별 트랙**으로 분리하고, **드럼은 다시 킥/스네어/하이햇/심벌/톰**으로
세분화해 주는 커맨드라인 도구입니다. 밴드 멤버가 곡을 파트별로 나눠 개별 연습
(내 파트만 듣기 / 내 파트만 빼고 듣기)에 쓰는 것을 목표로 합니다.

> A CLI that splits a song into per-instrument stems and further splits the drum
> stem into individual kit pieces, so band members can practice their part in
> isolation. (이 문서는 한국어 사용 가이드 중심입니다.)

---

## ⚡ 한눈에 (TL;DR)

```bash
# 1) 설치 (최초 1회)
brew install ffmpeg
uv venv --python 3.11 .venv && source .venv/bin/activate && uv pip install -e .

# 2) 곡 분리
bandprepare 내곡.mp3

# 3) 결과는 ./output/내곡/ 폴더에 생김
```

---

# 📖 사용 가이드 (How-to)

밴드 멤버 누구나 따라 할 수 있도록 단계별로 설명합니다. 터미널(Terminal)을 처음 써도
복사-붙여넣기만 하면 됩니다.

> 💡 **터미널 여는 법 (macOS)**: `⌘ + Space` → "터미널" 입력 → 엔터.

---

## STEP 1. 준비물

| 필요한 것 | 설명 | 확인 명령 |
|-----------|------|-----------|
| **ffmpeg** | mp3·m4a 같은 압축 음원을 읽는 데 필요 | `ffmpeg -version` |
| **Python 3.10 이상** | 프로그램 실행 환경 | `python3 --version` |
| **분리할 음원 파일** | mp3, wav, flac, m4a 등 | — |

- wav/flac만 쓸 거라면 ffmpeg 없이도 됩니다(하지만 설치를 권장).
- `uv`(빠른 파이썬 도구)가 있으면 설치가 가장 편합니다. 없으면 일반 `pip`도 OK.

---

## STEP 2. 설치하기

### macOS (Homebrew + uv, 권장)

```bash
# ffmpeg 설치
brew install ffmpeg

# 가상환경 만들고 BandPrepare 설치
uv venv --python 3.11 .venv
source .venv/bin/activate
uv pip install -e .
```

### uv가 없다면 (표준 pip)

```bash
brew install ffmpeg                 # (Ubuntu/Debian은: sudo apt install ffmpeg)
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
```

설치가 끝나면 다음이 보이면 성공입니다:

```bash
bandprepare --version
# bandprepare 0.1.0
```

> 📌 새 터미널을 열 때마다 `source .venv/bin/activate` 를 먼저 실행해야
> `bandprepare` 명령을 쓸 수 있습니다. (또는 `.venv/bin/bandprepare` 처럼 전체 경로 사용)

#### (선택) RoFormer 모델 쓰려면

`bs_roformer` / `mel_band_roformer` 를 쓸 때만 추가 의존성이 필요합니다(기본 설치엔 불포함):

```bash
uv pip install -e ".[roformer]"     # 또는: pip install -e ".[roformer]"
```

> 아키텍처와 설계 배경(특히 호환성 때문에 audio-separator를 쓰지 않은 이유)은
> [ARCHITECTURE.md](ARCHITECTURE.md) 를 참고하세요.

---

## STEP 3. 곡 분리하기 (첫 실행)

가장 기본 사용법 — 곡 파일 경로만 주면 됩니다.

```bash
bandprepare 내곡.mp3
```

> 💡 **파일 경로 쉽게 넣기**: `bandprepare ` 까지 친 뒤, Finder에서 음원 파일을
> 터미널 창으로 **드래그 앤 드롭**하면 경로가 자동으로 입력됩니다.

실행하면 두 단계가 순서대로 진행됩니다(진행 막대가 표시됩니다):

```
[1/2] 악기 분리 / Instrument separation (Demucs htdemucs_6s)
[2/2] 드럼 세부 분리 / Drum-kit separation (LarsNet)
```

> ⏱ **처음 한 번은 모델을 내려받느라 시간이 더 걸립니다** (Demucs 약 300MB +
> LarsNet 약 562MB). 한 번 받으면 캐시되어 다음부터는 빠릅니다.
> GPU 없이 CPU만 쓰면 곡 길이에 비례해 몇 분 걸릴 수 있어요(아래 성능 메모 참고).

---

## STEP 4. 결과물 확인하기

기본적으로 `./output/<곡이름>/` 폴더에 생깁니다.

```
output/내곡/
├── instruments/          ← 악기별 트랙
│   ├── vocals.wav        보컬
│   ├── bass.wav          베이스
│   ├── guitar.wav        기타
│   ├── piano.wav         피아노/건반
│   └── other.wav         그 외(신스 등)
└── drums/                ← 드럼을 또 쪼갠 것
    ├── kick.wav          킥(베이스 드럼)
    ├── snare.wav         스네어
    ├── hihat.wav         하이햇
    ├── cymbals.wav       크래쉬 + 라이드 심벌
    └── toms.wav          톰
```

각 파일은 그냥 음악 플레이어로 열어서 들으면 됩니다.

---

## STEP 5. 연습 목적별 사용법 (레시피)

### 🎤 내 파트만 듣기 (솔로 연습)

분리된 파일을 그대로 열면 됩니다. 예를 들어 베이시스트라면 `instruments/bass.wav`,
드러머라면 `drums/` 안의 파일들을 들으며 카피/연습하세요.

### 🎶 내 파트만 빼고 듣기 (마이너스원 백킹 트랙)

`--minus` 한 번이면 **내 악기만 빠진 합본 한 파일**이 바로 만들어집니다.
이걸 틀어 놓고 내 파트를 직접 연주하면 합주 연습이 돼요.
결과는 `output/<곡>/mixes/minus-<악기>.wav` 로 저장됩니다.

```bash
bandprepare 내곡.mp3 --minus bass          # 베이스 자리만 비운 합본
bandprepare 내곡.mp3 --minus vocals        # 보컬 뺀 MR(노래방 반주)
bandprepare 내곡.mp3 --minus vocals,bass   # 여러 개는 콤마로 (둘 다 비움)
```

**내 역할에 맞춰 고르세요** (기본 모델 `htdemucs_6s` 기준):

| 내 역할(빼고 싶은 것) | 명령 | 만들어지는 파일 |
|---|---|---|
| 보컬 / 노래방 MR | `--minus vocals` | `mixes/minus-vocals.wav` |
| 베이스 | `--minus bass` | `mixes/minus-bass.wav` |
| 기타 | `--minus guitar` | `mixes/minus-guitar.wav` |
| 건반/피아노 | `--minus piano` | `mixes/minus-piano.wav` |
| 드럼 | `--minus drums` | `mixes/minus-drums.wav` |
| 보컬 듀엣·기타 둘 다 | `--minus vocals,guitar` | `mixes/minus-vocals-guitar.wav` |

> 💡 **보컬을 더 깨끗하게 빼려면** 보컬 분리에 특화된 모델을 함께 쓰세요:
> ```bash
> bandprepare 내곡.mp3 --minus vocals --stem-model mel_band_roformer
> ```
> `mel_band_roformer` 는 보컬/반주 2스템 모델이라 잔여 보컬이 가장 적습니다
> (대신 RoFormer extra 설치 필요 — 아래 "분리 모델 바꾸기" 참고).

> 💡 휴대용으로 작게 받으려면 `--format mp3` 를, 드럼 세부 분리를 건너뛰어 더 빨리
> 만들려면 `--no-drum-split` 를 같이 주면 됩니다(마이너스 합본 결과는 동일).

> ℹ️ **동작 방식**: `원본 믹스 − 선택 스템들의 합` 으로 만듭니다(카라오케/마이너스원의
> 표준 방식). 원본에서 빼므로 잔향·공간감이 남아 자연스럽습니다.
> - 뺄 수 있는 악기는 `--stem-model` 에 따라 다릅니다(`--list-models` 로 확인).
> - `--stems`(개별 스템 저장)와는 **독립**이라, 저장하지 않은 악기도 뺄 수 있습니다.
> - 드럼은 통째로(`--minus drums`)만 가능하고, 킥·스네어 같은 **드럼 조각 단위는 아직 미지원**입니다.

<details>
<summary>대안 — DAW/ffmpeg로 직접 합치기 (수동)</summary>

`--minus` 대신 직접 섞고 싶다면, 음악 플레이어/DAW에 모든 트랙을 올리고 내 파트만
음소거해도 됩니다. ffmpeg로 합치려면 드럼을 통째로 받도록 `--no-drum-split` 으로 분리한 뒤
(그러면 `instruments/drums.wav` 도 생김) 원하는 트랙만 섞으세요. 예) **기타만 뺀 백킹**:

```bash
cd output/내곡/instruments
ffmpeg -i vocals.wav -i bass.wav -i piano.wav -i other.wav -i drums.wav \
  -filter_complex amix=inputs=5:normalize=0 ../기타뺀_백킹.wav
```

> `amix` 의 `normalize=0` 은 음량을 그대로 더합니다(소리가 크면 플레이어에서 줄이기).
> 드럼 세부 분리까지 한 상태에서 합치려면 분리 시 `--keep-drums-stem` 으로 원본
> `drums.wav` 를 남겨 두면 됩니다.

</details>

### 🥁 드럼 파트 연습 (킥·스네어 따로)

기본 실행만 해도 `drums/kick.wav`, `drums/snare.wav` … 가 만들어집니다.
드럼만 필요하면 드럼만 뽑아도 됩니다:

```bash
bandprepare 내곡.mp3 --stems drums
```

### 🎛 특정 악기만 뽑기

`--stems` 로 원하는 것만 고릅니다(콤마로 구분).

```bash
# 보컬 + 베이스만
bandprepare 내곡.mp3 --stems vocals,bass

# 보컬·드럼·베이스 (드럼은 자동으로 세부 분리됨)
bandprepare 내곡.mp3 --stems vocals,drums,bass
```

선택 가능한 스템은 **선택한 모델에 따라 다릅니다**(아래 "분리 모델 바꾸기" 참고).
기본 모델(`htdemucs_6s`)은 `vocals, drums, bass, guitar, piano, other` (또는 `all`).

### 🧠 분리 모델 바꾸기 (모델 선택)

1단계(악기)와 2단계(드럼)에 쓸 모델을 각각 고를 수 있습니다. 먼저 사용 가능한 모델 목록:

```bash
bandprepare --list-models
```

```bash
# 악기 분리 모델 바꾸기
bandprepare 내곡.mp3 --stem-model htdemucs_ft          # 4스템(보컬/드럼/베이스/other), 고품질
bandprepare 내곡.mp3 --stem-model bs_roformer          # 4스템, RoFormer (SOTA급)
bandprepare 내곡.mp3 --stem-model mel_band_roformer    # 보컬/반주 2스템 추출(보컬 품질 최상)

# 드럼 세부 분리 모델 바꾸기
bandprepare 내곡.mp3 --drum-model drumsep              # 4조각(kick/snare/toms/cymbals), MIT
bandprepare 내곡.mp3 --drum-model larsnet              # 5조각(+hihat), 기본값(비상업 라이선스)
bandprepare 내곡.mp3 --drum-model mdx23c               # 6조각(+ride/crash 분리), MIT
```

| 1단계 모델 | 스템 | 특징 | 라이선스 |
|-----------|------|------|----------|
| `htdemucs_6s` (기본) | 6 (vocals/drums/bass/**guitar/piano**/other) | 기타·피아노까지 분리 | MIT |
| `htdemucs_ft` | 4 (vocals/drums/bass/other) | Demucs 고품질 fine-tuned | MIT |
| `bs_roformer` | 4 (vocals/drums/bass/other) | RoFormer, SOTA급 품질 | MIT |
| `mel_band_roformer` | 2 (vocals/other) | 보컬/반주 추출 특화(최상) | MIT |

| 2단계 모델 | 조각 | 특징 | 라이선스 |
|-----------|------|------|----------|
| `larsnet` (기본) | 5 (kick/snare/**hihat**/cymbals/toms) | 하이햇 별도 분리 | **CC BY-NC(비상업)** |
| `drumsep` | 4 (kick/snare/toms/cymbals) | 하이햇 미분리, 상업 가능 | MIT |
| `mdx23c` | 6 (kick/snare/toms/**hihat/ride/crash**) | 라이드·크래시까지 분리(최다 조각), 상업 가능 | MIT |

> 💡 RoFormer 모델(`bs_roformer`/`mel_band_roformer`)은 추가 의존성이 필요합니다:
> `uv pip install -e ".[roformer]"` (또는 `pip install -e ".[roformer]"`).
> 첫 실행 시 체크포인트(약 500–870 MB)를 자동 다운로드해 `~/.cache/bandprepare/roformer` 에 캐시합니다.
> `mel_band_roformer`는 2스템(보컬/반주)이라 드럼 세부 분리가 자동으로 꺼집니다.

### 💾 mp3 / flac 로 받기

```bash
bandprepare 내곡.mp3 --format mp3     # 용량 작게
bandprepare 내곡.wav --format flac    # 무손실
```

### ⚡ 더 빠르게 돌리기

```bash
# 드럼 세부 분리(2단계) 생략 → 악기 6종만, 훨씬 빠름
bandprepare 내곡.mp3 --no-drum-split

# 드럼 Wiener 후처리 끄기 → 드럼 단계 가속(품질 약간 손해)
bandprepare 내곡.mp3 --no-drum-wiener
```

### 🔁 다시 실행하면?

이미 결과 파일이 다 있으면 자동으로 건너뜁니다. 다시 만들려면 `--overwrite` 를 붙이세요.

```bash
bandprepare 내곡.mp3 --overwrite
```

---

## STEP 6. 문제가 생기면 (FAQ / 트러블슈팅)

| 증상 | 원인 / 해결 |
|------|-------------|
| `command not found: bandprepare` | 가상환경 활성화를 안 함 → `source .venv/bin/activate` |
| `ffmpeg를 찾을 수 없습니다` | `brew install ffmpeg` 후 다시 실행 |
| mp3가 안 읽힘 | ffmpeg 미설치. 위와 동일 |
| 너무 느림 | GPU가 없으면 정상입니다. `--no-drum-split` 로 2단계를 생략하거나 짧은 구간으로 시험 |
| 첫 실행이 멈춘 듯함 | 모델(수백 MB) 내려받는 중일 수 있음. 네트워크 확인 후 기다리기 |
| 드럼 모델(562MB) 다운로드 실패 | 네트워크/Google Drive 일시 문제. 다시 실행하면 이어집니다 |
| Apple Silicon Mac인데 CPU로만 돎 | `--device mps` 로 강제 가능. (Intel Mac은 MPS가 느려서 일부러 CPU 사용) |

오류 메시지는 **한국어/영어 둘 다** 표시되고, 상황별 종료 코드를 반환합니다(맨 아래 표 참고).

---
---

# 📚 레퍼런스 (Reference)

## 주요 의존성 한눈에 / Dependencies at a glance

BandPrepare가 의존하는 외부 요소를 한 표로 정리합니다. **직접 설치가 필요한 것은
①②뿐**이고, ③ Python 패키지는 `pip install -e .` 가 자동 설치, ④ 모델 가중치는
첫 실행 시 자동 다운로드됩니다.

### ① 시스템 / 런타임 (직접 설치)

| 항목 | 조건 | 설치 | 필수? |
|------|------|------|-------|
| **ffmpeg** | — | `brew install ffmpeg` (Ubuntu/Debian: `apt install ffmpeg`) | mp3·m4a 등 압축 음원 입력 시 필수 (wav/flac만이면 선택) |
| **Python** | `>=3.10` | python.org / `brew` / pyenv 등 | ✅ 필수 |
| **uv** | — | [astral.sh/uv](https://docs.astral.sh/uv/) | 선택 (없으면 표준 `pip`) |

### ② Python 패키지 — base (`pip install -e .` 가 자동 설치)

| 패키지 | 버전 핀 | 역할 |
|--------|---------|------|
| `torch`, `torchaudio` | `>=2.1, <2.3` | 추론 엔진 (핀 사유는 아래 플랫폼 메모) |
| `demucs` | `==4.0.1` | Stage 1 악기 분리 + DrumSep 로딩 |
| `numpy` | `<2` | torch 2.2 ABI 호환 |
| `soundfile` | `>=0.12` | wav/flac 입출력 (libsndfile 번들, 별도 설치 불필요) |
| `pyyaml` | `>=6.0` | 벤더 모델 config 로딩 |
| `tqdm` | `>=4.65` | 진행 막대 |
| `gdown` | `>=5.1` | Google Drive 가중치 다운로드(LarsNet/DrumSep) |

> **선택 extra** `.[roformer]` — `bs_roformer`/`mel_band_roformer` 사용 시에만 필요:
> `rotary-embedding-torch`, `beartype`, `einops`, `librosa`,
> `numba (>=0.59,<0.61)`, `llvmlite (>=0.42,<0.44)`.
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
> 플랫폼 메모와 [ARCHITECTURE.md](ARCHITECTURE.md) §9를 참고하세요.

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

## 처리 파이프라인 / Pipeline

두 단계 모두 모델을 선택할 수 있습니다(`--stem-model`/`--drum-model`, `--list-models`).
기본값:

| 단계 | 기본 모델 | 출력 |
|------|------|------|
| **1. 악기 분리** | [Demucs `htdemucs_6s`](https://github.com/facebookresearch/demucs) | `vocals`, `drums`, `bass`, `guitar`, `piano`, `other` |
| **2. 드럼 세부 분리** | [LarsNet](https://github.com/polimi-ispl/larsnet) | `kick`, `snare`, `hihat`, `cymbals`(크래쉬+라이드), `toms` |

선택 가능한 모델 전체는 STEP 5의 "분리 모델 바꾸기" 표를 참고하세요
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

## 개발 / Development

```bash
uv pip install -e ".[dev]"
pytest -q                      # 모델 없이 도는 빠른 단위 테스트
```

`pytest` 단위 테스트는 모델 가중치 없이 도는 빠른 테스트만 포함합니다(인자 파싱,
출력 경로 계획, 장치 해석, 샘플 생성 등). 실제 분리는 위 "동작 확인" 절차로 수행합니다.

### 구조

자세한 설계·데이터 흐름·설계 결정(특히 호환성 때문에 audio-separator 미사용)은
[ARCHITECTURE.md](ARCHITECTURE.md) 참고.

```
src/bandprepare/
├── cli.py                 # 인자 파싱 / 진입점
├── pipeline.py            # 단계 오케스트레이션
├── audio.py               # 입출력 / ffmpeg 점검
├── device.py              # --device 해석
├── separation/
│   ├── base.py            # Separator 프로토콜 + ModelInfo
│   ├── registry.py        # 모델 카탈로그(--stem-model/--drum-model/--list-models)
│   ├── download.py        # 가중치 다운로드/캐시 공용 헬퍼
│   ├── stems.py           # Demucs 백엔드 (htdemucs_6s/htdemucs_ft)
│   ├── roformer.py        # RoFormer 백엔드 (bs_roformer/mel_band_roformer)
│   ├── drums.py           # LarsNet 백엔드
│   └── drumsep.py         # DrumSep(inagoy) 백엔드
└── vendor/
    ├── larsnet/           # 벤더링된 LarsNet 모델 코드
    └── roformer/          # 벤더링된 BS/Mel-Band RoFormer (ZFTurbo v1.0.12, MIT)
```
