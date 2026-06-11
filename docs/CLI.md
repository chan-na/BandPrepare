# BandPrepare — 커맨드라인(CLI) 사용 가이드

밴드 멤버 누구나 따라 할 수 있도록 단계별로 설명합니다. 터미널(Terminal)을 처음 써도
복사-붙여넣기만 하면 됩니다. 마우스로 쓰고 싶다면 [GUI 가이드](GUI.md)를, 옵션·모델·
라이선스 등 자세한 내용은 [레퍼런스](REFERENCE.md)를 참고하세요.

> 💡 **터미널 여는 법 (macOS)**: `⌘ + Space` → "터미널" 입력 → 엔터.

> A step-by-step CLI guide (Korean-first). Prefer the mouse? See the
> [GUI guide](GUI.md). Full options, models and licenses live in the
> [reference](REFERENCE.md).

---

## STEP 1. 준비물

| 필요한 것 | 설명 | 확인 명령 |
|-----------|------|-----------|
| **Python 3.10 이상** | 프로그램 실행 환경 | `python3 --version` |
| **분리할 음원 파일** | mp3, wav, flac, m4a 등 | — |

- `uv`(빠른 파이썬 도구)가 있으면 설치가 가장 편합니다. 없으면 일반 `pip`도 OK.

---

## STEP 2. 설치하기

### macOS (Homebrew + uv, 권장)

```bash
# 가상환경 만들고 BandPrepare 설치
uv venv --python 3.11 .venv
source .venv/bin/activate
uv pip install -e .
```

### uv가 없다면 (표준 pip)

```bash
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
> [ARCHITECTURE.md](../ARCHITECTURE.md) 를 참고하세요.

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
> GPU 없이 CPU만 쓰면 곡 길이에 비례해 몇 분 걸릴 수 있어요
> ([레퍼런스의 성능 메모](REFERENCE.md#성능-메모--performance-notes) 참고).

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

> ⚖️ 모델별 출처·라이선스 전체는 [레퍼런스의 "모델 출처 / 라이선스"](REFERENCE.md#모델-출처--라이선스--model-sources--licenses)를 참고하세요.

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

### 🚀 GPU 가속 (CUDA) — Linux / Windows

다운로드한 **포터블 릴리스 번들은 CPU 전용 torch**를 씁니다(용량을 작게 유지 — 어디서나
설치 없이 바로 실행). NVIDIA GPU로 몇 배 빠르게 돌리려면 **pip로 CUDA 빌드 torch를 직접
설치**하면 됩니다(필요할 때만 CUDA 런타임을 내려받는 방식). NVIDIA 드라이버가 설치돼 있어야
합니다.

```bash
# 1) CUDA 빌드 torch 설치 (드라이버에 맞는 CUDA 버전 선택 — 예: cu121 = CUDA 12.1)
pip install "torch>=2.1.0,<2.3.0" "torchaudio>=2.1.0,<2.3.0" \
  --index-url https://download.pytorch.org/whl/cu121

# 2) BandPrepare 설치 (RoFormer 모델까지 쓰려면 ".[roformer]")
pip install -e .

# 3) GPU로 실행
bandprepare 내곡.mp3 --device cuda
```

> 💡 **macOS**는 CUDA가 없습니다. Apple Silicon은 `--device mps` 로 GPU(Metal)를 씁니다
> (Intel Mac은 MPS가 느려 일부러 CPU 사용). CUDA는 **Linux / Windows + NVIDIA GPU** 전용입니다.

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
| 너무 느림 | GPU가 없으면 정상입니다. `--no-drum-split` 로 2단계를 생략하거나 짧은 구간으로 시험 |
| 첫 실행이 멈춘 듯함 | 모델(수백 MB) 내려받는 중일 수 있음. 네트워크 확인 후 기다리기 |
| 드럼 모델(562MB) 다운로드 실패 | 네트워크/Google Drive 일시 문제. 다시 실행하면 이어집니다 |
| 모델 다운로드가 `CERTIFICATE_VERIFY_FAILED` (SSL)로 실패 | 최신 릴리스는 자동 해결됨. 구버전 번들이면 임시로 앞에 `SSL_CERT_FILE="<받은폴더>/_internal/certifi/cacert.pem"` 를 붙여 실행 |
| Apple Silicon Mac인데 CPU로만 돎 | `--device mps` 로 강제 가능. (Intel Mac은 MPS가 느려서 일부러 CPU 사용) |

오류 메시지는 **한국어/영어 둘 다** 표시되고, 상황별 종료 코드를 반환합니다
([레퍼런스의 "오류 처리 / Exit codes"](REFERENCE.md#오류-처리--exit-codes) 참고).

---

> 🖱 마우스로 쓰고 싶다면 → [GUI 가이드](GUI.md) · 📚 옵션·모델·라이선스 → [레퍼런스](REFERENCE.md)
