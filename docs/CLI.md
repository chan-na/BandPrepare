# BandPrepare — 커맨드라인(CLI) 사용 가이드

밴드 멤버 누구나 따라 할 수 있도록 단계별로 설명합니다. **설치 없이** 릴리스에서 포터블
앱을 받아 압축만 풀면 바로 씁니다(Python·ffmpeg·torch 모두 내장). 터미널을 처음 써도
복사-붙여넣기만 하면 됩니다. 마우스로 쓰고 싶다면 [GUI 가이드](GUI.md)를, 옵션·모델·
라이선스 등 자세한 내용은 [레퍼런스](REFERENCE.md)를 참고하세요.

> 💡 **터미널 여는 법 (macOS)**: `⌘ + Space` → "터미널" 입력 → 엔터.

> A step-by-step CLI guide (Korean-first) for the **portable bundle** — no Python
> or ffmpeg install needed. Prefer the mouse? See the [GUI guide](GUI.md). Full
> options, models and licenses live in the [reference](REFERENCE.md). To build or
> install from source instead, see the [dev guide](DEVELOPMENT.md).

---

## STEP 1. 준비물

| 필요한 것 | 설명 |
|-----------|------|
| **분리할 음원 파일** | mp3, wav, flac, m4a 등 — **또는 유튜브/URL 링크**(자동 다운로드) |
| **인터넷 연결** | 첫 실행 때 모델 가중치를 내려받습니다(이후엔 캐시되어 오프라인 가능). 유튜브 링크를 쓸 땐 다운로드에도 필요합니다 |

- 포터블 앱에는 Python·ffmpeg·torch·RoFormer 모델이 들어 있어 **따로 설치할 게 없습니다.**
- 소스에서 직접 빌드·설치하려면 [개발 가이드](DEVELOPMENT.md)를 보세요.

---

## STEP 2. 받아서 준비하기 (포터블 앱)

### 1) 릴리스에서 내 OS용 파일 받기

[Releases](../../../releases) 페이지에서 내 컴퓨터에 맞는 파일을 받습니다.

| 내 컴퓨터 | 받을 파일 |
|-----------|-----------|
| **맥 (애플 실리콘 · M1/M2/M3…)** | `bandprepare-macos-arm64-<버전>.zip` |
| **맥 (인텔)** | `bandprepare-macos-x86_64-<버전>.zip` |
| **리눅스 (NVIDIA GPU 없음)** | `bandprepare-linux-cpu-only-<버전>.tar.gz` |
| **리눅스 + NVIDIA GPU** | `bandprepare-linux-cuda-<버전>.tar.gz.001` · `.002` … (여러 조각 — 아래 2-1 참고) |
| **윈도우 (NVIDIA GPU 없음)** | `bandprepare-windows-cpu-only-<버전>.zip` |
| **윈도우 + NVIDIA GPU** | `bandprepare-windows-cuda-<버전>.zip.001` · `.002` … (여러 조각 — 아래 2-1 참고) |

> 🚀 **NVIDIA GPU가 있나요?** `…-cuda` 번들을 받으면 GPU(CUDA) 가속을 **설치 없이** 바로 씁니다
> (`auto` 가 자동으로 GPU 선택, GPU가 없으면 CPU로 폴백). 다만 용량이 커서 **여러 조각으로 나뉘어**
> 올라오니, 받은 뒤 하나로 합쳐야 합니다(아래 **2-1**). GPU가 없다면 더 가벼운 `…-cpu-only` 를 받으세요.

> 🍎 macOS는 **`BandPrepare.app`**(GUI 앱) 하나로 배포됩니다. CLI도 그 앱 안에 함께 들어 있어요.
> (macOS에는 CUDA가 없고, 애플 실리콘은 Metal(MPS)을 씁니다 — `-cuda` 번들은 macOS용이 아닙니다.)

> 📌 릴리스는 검토를 위해 **비공개(draft)로 먼저 올라옵니다.** 자산이 아직 안 보이면
> 공개 전일 수 있습니다 — 이럴 땐 [소스에서 설치](DEVELOPMENT.md)해 쓰세요.

### 2) 압축 풀기

> #### 2-1) `…-cuda` 번들을 받았다면 — 먼저 조각 합치기
>
> CUDA 번들은 용량 때문에 `.001`, `.002` … 여러 조각으로 나뉘어 있습니다. 받은 조각을 **순서대로
> 하나로 이어 붙인 뒤** 평소처럼 압축을 풉니다(추가 프로그램 불필요). `…-cpu-only`·macOS 번들은
> 이 단계가 필요 없습니다.
>
> ```bash
> # Linux / macOS — 조각을 합쳐 하나의 .tar.gz 로 만든 뒤 풀기
> cat bandprepare-linux-cuda-*.tar.gz.* > bandprepare-linux-cuda.tar.gz
> tar xzf bandprepare-linux-cuda.tar.gz        # → bandprepare/ 폴더
> ```
> ```bat
> :: Windows — 명령 프롬프트(cmd)에서 copy /b 로 합친 뒤 압축 해제
> copy /b bandprepare-windows-cuda-<버전>.zip.001 + bandprepare-windows-cuda-<버전>.zip.002 bandprepare-windows-cuda.zip
> :: 조각이 .003 이상 더 있으면 + 로 순서대로 이어 붙이세요. 이후 탐색기에서 우클릭 → 압축 풀기
> ```

**macOS**: 압축을 풀면 **`BandPrepare.app`** 이 나옵니다. CLI는 그 앱 패키지 안에 있습니다 —
`BandPrepare.app/Contents/MacOS/bandprepare-cli`. 매번 긴 경로를 치지 않도록 앱 옆에 **단축
링크**를 하나 만들어 두면 이 가이드의 `./bandprepare-cli ...` 예시를 그대로 쓸 수 있습니다:

```bash
ln -s "BandPrepare.app/Contents/MacOS/bandprepare-cli" bandprepare-cli
```

**Linux·Windows**: 압축을 풀면 **`bandprepare/` 폴더 하나**가 나오고, 그 안에 실행 파일 두 개가 있습니다:

```
bandprepare/
├── bandprepare-cli      ← 터미널용 CLI (이 가이드에서 쓰는 것)
├── bandprepare          ← 더블클릭용 GUI (GUI 가이드 참고)
└── _internal/           ← 내부 라이브러리 (건드리지 않음)
```

> ⚠️ **이름 주의**: 접미사 **없는** `bandprepare` 는 **GUI**, 터미널용 CLI는 `bandprepare-cli` 예요.
> (윈도우는 각각 `bandprepare.exe`, `bandprepare-cli.exe`. macOS는 위 단축 링크 `bandprepare-cli`
> 또는 `BandPrepare.app/Contents/MacOS/bandprepare-cli`.)

### 3) 첫 실행 경고 우회 (한 번만)

받은 앱은 정식 서명/공증이 안 돼 있어 첫 실행 때 OS가 막을 수 있습니다. 한 번만 풀어 주면 됩니다.

- **macOS**: 다운로드 격리 때문에 막힙니다. **`BandPrepare.app` 을 우클릭 → 열기 → 열기** 하면
  앱 전체가 한 번에 허용됩니다(ad-hoc 서명된 단일 번들이라, 폴더 시절처럼 개별 라이브러리까지
  풀 필요가 없습니다). 터미널을 선호하면:
  ```bash
  xattr -dr com.apple.quarantine BandPrepare.app
  ```
- **Windows**: SmartScreen "Windows의 PC 보호" → **추가 정보 → 실행**. (백신이 오탐하면 신뢰 목록에 추가.)
- **Linux**: 경고 없음. 필요 시 `chmod +x ./bandprepare/bandprepare-cli`.

> 자세한 배경은 [개발 가이드의 "다운로드한 릴리스 첫 실행"](DEVELOPMENT.md#다운로드한-릴리스-첫-실행-서명-경고-우회)에 있습니다.

---

## STEP 3. 곡 분리하기 (첫 실행)

압축을 푼 위치에서 CLI를 실행합니다. 가장 기본 사용법 — 곡 파일 경로만 주면 됩니다.

```bash
# macOS: BandPrepare.app 과 단축 링크를 만든 폴더에서
cd /받은경로
./bandprepare-cli 내곡.mp3          # 링크 없이 쓰려면 BandPrepare.app/Contents/MacOS/bandprepare-cli

# Linux·Windows: 압축 푼 bandprepare 폴더 안에서
cd /받은경로/bandprepare
./bandprepare-cli 내곡.mp3          # 윈도우: bandprepare-cli.exe 내곡.mp3
```

> 💡 **파일 경로 쉽게 넣기**: `./bandprepare-cli ` 까지 친 뒤, Finder/탐색기에서 음원
> 파일을 터미널 창으로 **드래그 앤 드롭**하면 경로가 자동으로 입력됩니다.

> 📌 아래 예시는 `bandprepare-cli` 로 줄여 씁니다. 실제로는 **위처럼 폴더 안에서
> `./bandprepare-cli`** 로 실행하거나 전체 경로(`/받은경로/bandprepare/bandprepare-cli`)를
> 쓰면 됩니다.

실행하면 악기 분리가 진행됩니다(진행 막대가 표시됩니다):

```
[1/1] 악기 분리 / Instrument separation (Demucs htdemucs_ft)
```

드럼을 킥/스네어 등 조각으로 더 쪼개려면 `--drum-split` 를 주세요. 그러면 2단계가
추가됩니다(기본은 꺼져 있음):

```
[1/2] 악기 분리 / Instrument separation (Demucs htdemucs_ft)
[2/2] 드럼 세부 분리 / Drum-kit separation (MDX23C DrumSep)
```

> ⏱ **처음 한 번은 모델을 내려받느라 시간이 더 걸립니다** (Demucs 약 300MB,
> `--drum-split` 사용 시 MDX23C 약 438MB 추가). 한 번 받으면 캐시되어 다음부터는 빠릅니다(번들 바깥
> `~/.cache/bandprepare` 등에 저장 — 앱을 옮기거나 지워도 유지).
> GPU 없이 CPU만 쓰면 곡 길이에 비례해 몇 분 걸릴 수 있어요
> ([레퍼런스의 성능 메모](REFERENCE.md#성능-메모--performance-notes) 참고).

---

## STEP 4. 결과물 확인하기

기본적으로 **입력 파일 옆** `BandPrepareOutput/<곡이름>/` 폴더에 생깁니다
(`-o` 로 바꿀 수 있습니다).

```
BandPrepareOutput/내곡/
└── instruments/          ← 악기별 트랙
    ├── vocals.wav        보컬
    ├── bass.wav          베이스
    ├── other.wav         그 외(기타·건반·신스 등)
    └── drums.wav         드럼 전체
```

`--drum-split` 를 주면 드럼을 또 쪼갠 `drums/` 폴더가 추가됩니다:

```
BandPrepareOutput/내곡/
├── instruments/
│   └── drums.wav         드럼 전체(기본 보존, --no-keep-drums-stem 시 제외)
└── drums/                ← 드럼을 또 쪼갠 것 (--drum-split)
    ├── kick.wav          킥(베이스 드럼)
    ├── snare.wav         스네어
    ├── toms.wav          톰
    ├── hihat.wav         하이햇
    ├── ride.wav          라이드 심벌
    └── crash.wav         크래쉬 심벌
```

각 파일은 그냥 음악 플레이어로 열어서 들으면 됩니다.

> 💡 기타·피아노를 별도 트랙으로 받고 싶으면 6스템 모델을 쓰세요:
> `--stem-model htdemucs_6s` (아래 "분리 모델 바꾸기" 참고).

---

## STEP 5. 연습 목적별 사용법 (레시피)

### 🔗 유튜브 링크에서 바로 분리

파일 경로 대신 **유튜브(또는 다른 사이트) 링크**를 그대로 주면, 음원을 자동으로
내려받아 분리합니다. 링크는 따옴표로 감싸세요(`&` 등 특수문자 보호).

```bash
bandprepare-cli "https://www.youtube.com/watch?v=VIDEO_ID"
bandprepare-cli "https://youtu.be/VIDEO_ID" --stems vocals,drums --drum-split
```

- 받은 음원은 **결과 폴더에 `source.<확장자>` 로 함께 저장**되어 다시 듣거나 재처리할 수 있습니다.
- 출력 폴더를 `-o` 로 지정하지 않으면 **현재 폴더의 `BandPrepareOutput/<영상 제목>/`** 에 만들어집니다.
- `--minus`, `--stem-model` 등 **모든 옵션을 파일 입력과 똑같이** 쓸 수 있습니다.

> ⚠️ **본인이 권리를 가졌거나 허용된 콘텐츠만** 내려받아 개인 연습 용도로 사용하세요.
> 다운로드는 내장 yt-dlp 가 처리합니다 — 유튜브 변경으로 막히면 최신 릴리스로 갱신하세요
> (소스/pip 설치 시에는 `pip install -U yt-dlp`).

### 🎤 내 파트만 듣기 (솔로 연습)

분리된 파일을 그대로 열면 됩니다. 예를 들어 베이시스트라면 `instruments/bass.wav`,
드러머라면 `--drum-split` 로 분리한 `drums/` 안의 파일들을 들으며 카피/연습하세요.

### 🎶 내 파트만 빼고 듣기 (마이너스원 백킹 트랙)

`--minus` 한 번이면 **내 악기만 빠진 합본 한 파일**이 바로 만들어집니다.
이걸 틀어 놓고 내 파트를 직접 연주하면 합주 연습이 돼요.
결과는 `BandPrepareOutput/<곡>/mixes/minus-<악기>.wav` 로 저장됩니다.

```bash
bandprepare-cli 내곡.mp3 --minus bass          # 베이스 자리만 비운 합본
bandprepare-cli 내곡.mp3 --minus vocals        # 보컬 뺀 MR(노래방 반주)
bandprepare-cli 내곡.mp3 --minus vocals,bass   # 여러 개는 콤마로 (둘 다 비움)
```

**내 역할에 맞춰 고르세요** (기본 모델 `htdemucs_ft` 는 vocals/drums/bass/other —
기타·건반을 빼려면 6스템 모델 `--stem-model htdemucs_6s` 를 함께 쓰세요):

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
> bandprepare-cli 내곡.mp3 --minus vocals --stem-model mel_band_roformer
> ```
> `mel_band_roformer` 는 보컬/반주 2스템 모델이라 잔여 보컬이 가장 적습니다
> (RoFormer 모델은 **포터블 앱에 포함**되어 별도 설치가 필요 없습니다).

> 💡 휴대용으로 작게 받으려면 `--format mp3` 를 같이 주면 됩니다.

> ℹ️ **동작 방식**: `원본 믹스 − 선택 스템들의 합` 으로 만듭니다(카라오케/마이너스원의
> 표준 방식). 원본에서 빼므로 잔향·공간감이 남아 자연스럽습니다.
> - 뺄 수 있는 악기는 `--stem-model` 에 따라 다릅니다(`--list-models` 로 확인).
> - `--stems`(개별 스템 저장)와는 **독립**이라, 저장하지 않은 악기도 뺄 수 있습니다.
> - 드럼은 통째로(`--minus drums`)만 가능하고, 킥·스네어 같은 **드럼 조각 단위는 아직 미지원**입니다.

#### 🥁 박자 카운트인 넣기 (`--count-in`)

마이너스원을 틀자마자 음악이 바로 시작하면 박자를 맞춰 들어가기 어렵습니다.
`--count-in <BPM>` 을 주면 합본 **맨 앞에 그 템포의 클릭(삐 삐 삐 삐)** 이 붙어,
밴드가 박자를 세고 다음 첫 박에 함께 들어갈 수 있습니다.
**곡의 BPM 은 직접 입력**합니다(자동 감지 아님).

```bash
bandprepare-cli 내곡.mp3 --minus bass --count-in 120         # 1마디(4박) 카운트인 후 시작
bandprepare-cli 내곡.mp3 --minus vocals --count-in 90 --count-in-bars 2   # 2마디(8박)
bandprepare-cli 내곡.mp3 --minus drums --count-in 140 --count-in-beats 3  # 3/4박자
```

- 첫 박(다운비트)은 더 높은 음·큰 음량으로 구분되고, 카운트인 길이만큼 박을 센 뒤
  **바로 다음 박에 원곡이 시작**됩니다(예: 120 BPM·1마디 → 클릭 2초 + 원곡).
- 파일명에 템포가 표시됩니다: `mixes/minus-bass-count120.wav`
  (카운트인 없는 `minus-bass.wav` 와 별도 파일이라 덮어쓰지 않습니다).
- `--minus` 가 있어야 적용됩니다(없으면 무시).

<details>
<summary>대안 — DAW/ffmpeg로 직접 합치기 (수동)</summary>

`--minus` 대신 직접 섞고 싶다면, 음악 플레이어/DAW에 모든 트랙을 올리고 내 파트만
음소거해도 됩니다. ffmpeg로 합치려면 기본 분리 결과(`instruments/drums.wav` 포함)에서
원하는 트랙만 섞으세요.
예) **기타만 뺀 백킹** (6스템 모델 `--stem-model htdemucs_6s` 로 분리한 경우):

```bash
cd BandPrepareOutput/내곡/instruments
ffmpeg -i vocals.wav -i bass.wav -i piano.wav -i other.wav -i drums.wav \
  -filter_complex amix=inputs=5:normalize=0 ../기타뺀_백킹.wav
```

> `amix` 의 `normalize=0` 은 음량을 그대로 더합니다(소리가 크면 플레이어에서 줄이기).
> `--drum-split` 로 드럼을 세부 분리한 상태에서도 원본 `drums.wav` 는 기본으로 함께
> 저장되므로 그대로 합치면 됩니다(저장하지 않으려면 `--no-keep-drums-stem`).
> (`ffmpeg` 는 별도로 설치해야 합니다 — 포터블 앱 안의 ffmpeg는 BandPrepare 전용입니다.)

</details>

### 🥁 드럼 파트 연습 (킥·스네어 따로)

`--drum-split` 를 주면 `drums/kick.wav`, `drums/snare.wav` … 가 만들어집니다.
드럼만 필요하면 드럼만 뽑아도 됩니다:

```bash
bandprepare-cli 내곡.mp3 --drum-split --stems drums
```

### 🎛 특정 악기만 뽑기

`--stems` 로 원하는 것만 고릅니다(콤마로 구분).

```bash
# 보컬 + 베이스만
bandprepare-cli 내곡.mp3 --stems vocals,bass

# 보컬·드럼·베이스 (--drum-split 를 더하면 드럼은 세부 분리도 됨)
bandprepare-cli 내곡.mp3 --stems vocals,drums,bass
```

선택 가능한 스템은 **선택한 모델에 따라 다릅니다**(아래 "분리 모델 바꾸기" 참고).
기본 모델(`htdemucs_ft`)은 `vocals, drums, bass, other` (또는 `all`);
`htdemucs_6s` 를 고르면 `guitar, piano` 가 추가됩니다.

### 🧠 분리 모델 바꾸기 (모델 선택)

1단계(악기)와 2단계(드럼)에 쓸 모델을 각각 고를 수 있습니다. 먼저 사용 가능한 모델 목록:

```bash
bandprepare-cli --list-models
```

```bash
# 악기 분리 모델 바꾸기
bandprepare-cli 내곡.mp3 --stem-model htdemucs_6s          # 6스템(기타/피아노까지 분리)
bandprepare-cli 내곡.mp3 --stem-model bs_roformer          # 4스템, RoFormer (SOTA급)
bandprepare-cli 내곡.mp3 --stem-model mel_band_roformer    # 보컬/반주 2스템 추출(보컬 품질 최상)

# 드럼 세부 분리 모델 바꾸기 (--drum-split 와 함께 쓸 때 적용됨)
bandprepare-cli 내곡.mp3 --drum-split --drum-model drumsep   # 4조각(kick/snare/toms/cymbals), MIT
bandprepare-cli 내곡.mp3 --drum-split --drum-model larsnet   # 5조각(+hihat), 비상업 라이선스
bandprepare-cli 내곡.mp3 --drum-split --drum-model mdx23c    # 6조각(+ride/crash 분리), 기본값, MIT
```

| 1단계 모델 | 스템 | 특징 | 라이선스 |
|-----------|------|------|----------|
| `htdemucs_ft` (기본) | 4 (vocals/drums/bass/other) | Demucs 고품질 fine-tuned | MIT |
| `htdemucs_6s` | 6 (vocals/drums/bass/**guitar/piano**/other) | 기타·피아노까지 분리 | MIT |
| `bs_roformer` | 4 (vocals/drums/bass/other) | RoFormer, SOTA급 품질 | MIT |
| `mel_band_roformer` | 2 (vocals/other) | 보컬/반주 추출 특화(최상) | MIT |

| 2단계 모델 | 조각 | 특징 | 라이선스 |
|-----------|------|------|----------|
| `mdx23c` (기본) | 6 (kick/snare/toms/**hihat/ride/crash**) | 라이드·크래시까지 분리(최다 조각), 상업 가능 | MIT |
| `larsnet` | 5 (kick/snare/**hihat**/cymbals/toms) | 하이햇 별도 분리 | **CC BY-NC(비상업)** |
| `drumsep` | 4 (kick/snare/toms/cymbals) | 하이햇 미분리, 상업 가능 | MIT |

> 💡 RoFormer 모델(`bs_roformer`/`mel_band_roformer`)은 **포터블 앱에 포함**되어 별도
> 설치가 필요 없습니다. 첫 실행 시 체크포인트(약 500–870 MB)를 자동 다운로드해
> `~/.cache/bandprepare/roformer` 에 캐시합니다.
> `mel_band_roformer`는 2스템(보컬/반주)이라 드럼 세부 분리가 자동으로 꺼집니다.

> ⚖️ 모델별 출처·라이선스 전체는 [레퍼런스의 "모델 출처 / 라이선스"](REFERENCE.md#모델-출처--라이선스--model-sources--licenses)를 참고하세요.

### 💾 mp3 / flac 로 받기

```bash
bandprepare-cli 내곡.mp3 --format mp3     # 용량 작게
bandprepare-cli 내곡.wav --format flac    # 무손실
```

### ⚡ 더 빠르게 돌리기

드럼 세부 분리(2단계)는 기본으로 꺼져 있어 기본 실행이 가장 빠릅니다
(`--drum-split` 를 줬을 때만 2단계가 돕니다).

```bash
# 드럼 Wiener 후처리 끄기 → 드럼 단계 가속(품질 약간 손해, larsnet 전용)
bandprepare-cli 내곡.mp3 --drum-split --drum-model larsnet --no-drum-wiener
```

### 🚀 GPU 가속 — 어떤 장치를 쓰나

- **NVIDIA GPU (Linux · Windows)**: `…-cuda` 포터블 번들을 받으면 GPU(CUDA) 가속을 **설치 없이**
  바로 씁니다. 기본값 `auto` 가 CUDA를 자동 선택하므로 옵션을 따로 줄 필요가 없습니다(명시하려면
  `--device cuda`). GPU가 없으면 자동으로 CPU로 폴백하므로, `-cuda` 번들은 CPU 전용 번들의 상위호환입니다.
  ```bash
  bandprepare-cli 내곡.mp3 --device cuda     # NVIDIA GPU 가속 (cuda 번들)
  ```
  > `-cuda` 번들은 용량 때문에 여러 조각으로 나뉘어 배포됩니다 — 받는 법·합치는 법은 위 **STEP 2**를
  > 참고하세요. GPU가 없다면 더 가벼운 `…-cpu-only` 번들을 받으면 됩니다. 소스에서 직접 CUDA torch를
  > 골라 설치하려면 → [개발 가이드의 "GPU 가속 (CUDA)"](DEVELOPMENT.md#gpu-가속-cuda).
- **macOS 포터블 앱**은 Apple Silicon에서 `--device mps` 로 GPU(Metal) 가속을 씁니다
  (`auto` 가 자동 선택). macOS에는 CUDA가 없습니다.
  ```bash
  bandprepare-cli 내곡.mp3 --device mps     # 애플 실리콘에서 Metal 가속
  ```
  Intel Mac은 MPS가 느려 `auto` 가 일부러 CPU를 선택합니다.

### 🔁 다시 실행하면?

이미 결과 파일이 다 있으면 자동으로 건너뜁니다. 다시 만들려면 `--overwrite` 를 붙이세요.

```bash
bandprepare-cli 내곡.mp3 --overwrite
```

---

## STEP 6. 문제가 생기면 (FAQ / 트러블슈팅)

| 증상 | 원인 / 해결 |
|------|-------------|
| `command not found` / `bandprepare-cli: No such file` | Linux·Windows는 압축 푼 `bandprepare/` 폴더 안에서 `./bandprepare-cli` 로 실행하거나 전체 경로 사용. macOS는 단축 링크(STEP 2-2)나 `BandPrepare.app/Contents/MacOS/bandprepare-cli`. |
| macOS: `library load disallowed by system policy` 또는 앱이 안 열림 | 다운로드 격리 때문 → `BandPrepare.app` **우클릭 → 열기**, 또는 `xattr -dr com.apple.quarantine BandPrepare.app` (STEP 2-3 참고) |
| Linux/macOS: `Permission denied` | 실행 권한 부여 → `chmod +x ./bandprepare-cli` |
| 너무 느림 | GPU가 없으면 정상입니다. **NVIDIA GPU가 있으면 `…-cuda` 번들**로 몇 배 빨라집니다(STEP 2). 2단계(드럼 세부 분리)는 기본으로 꺼져 있으니 `--drum-split` 없이 돌리거나 짧은 구간으로 시험 |
| 첫 실행이 멈춘 듯함 | 모델(수백 MB) 내려받는 중일 수 있음. 네트워크 확인 후 기다리기 |
| 드럼 모델 다운로드 실패 | 네트워크 일시 문제 — 다시 실행하면 이어집니다. `larsnet`/`drumsep` 은 **Google Drive**에서 받으므로 사내망 등에서 막힐 수 있습니다(기본 `mdx23c` 는 HuggingFace) |
| 모델 다운로드가 `CERTIFICATE_VERIFY_FAILED` (SSL)로 실패 | 최신 릴리스는 자동 해결됨. 구버전 번들이면 임시로 앞에 `SSL_CERT_FILE="<받은폴더>/_internal/certifi/cacert.pem"` 를 붙여 실행 |
| Apple Silicon Mac인데 CPU로만 돎 | `--device mps` 로 강제 가능. (Intel Mac은 MPS가 느려서 일부러 CPU 사용) |

오류 메시지는 **한국어/영어 둘 다** 표시되고, 상황별 종료 코드를 반환합니다
([레퍼런스의 "오류 처리 / Exit codes"](REFERENCE.md#오류-처리--exit-codes) 참고).

---

> 🖱 마우스로 쓰고 싶다면 → [GUI 가이드](GUI.md) · 📚 옵션·모델·라이선스 → [레퍼런스](REFERENCE.md) · 🛠 소스 설치·빌드·GPU → [개발 가이드](DEVELOPMENT.md)
