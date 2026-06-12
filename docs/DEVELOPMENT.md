# BandPrepare — 개발 / 빌드 / 릴리스 가이드

개발 환경 셋업, 테스트, 포터블 앱 빌드(PyInstaller), 다운로드한 릴리스의 첫 실행
(서명 경고 우회), 소스 트리 구조를 다룹니다. 내부 설계·데이터 흐름·설계 결정은
[ARCHITECTURE.md](../ARCHITECTURE.md)를 참고하세요.

> Dev setup, tests, portable-app build (PyInstaller), first-run signing-warning
> workarounds, and source layout. For internal design see
> [ARCHITECTURE.md](../ARCHITECTURE.md).

> 💡 대부분의 사용자는 [Releases](../../../releases)의 **포터블 앱**을 받아 쓰면 됩니다
> ([CLI](CLI.md) / [GUI](GUI.md) 가이드). 이 문서는 **소스에서 직접 빌드·설치**하거나
> **GPU(CUDA) 가속**·**포터블 번들 빌드**가 필요한 경우를 위한 정본입니다.

---

## 소스에서 설치 / Install from source

소스에서 설치하면 최신 코드를 쓰거나 GPU(CUDA) torch를 직접 고를 수 있습니다.

### 준비물

| 필요한 것 | 조건 |
|-----------|------|
| **Python** | `>=3.10` (python.org / `brew` / pyenv 등) |
| **uv** *(선택)* | 빠른 설치 도구 — 없으면 표준 `pip` 사용 |

### 가상환경 + 설치

```bash
# uv (권장)
uv venv --python 3.11 .venv
source .venv/bin/activate
uv pip install -e .

# uv가 없다면 (표준 pip)
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
```

설치가 끝나면 다음이 보이면 성공입니다:

```bash
bandprepare --version
# bandprepare 0.1.0
```

> 📌 새 터미널을 열 때마다 `source .venv/bin/activate` 를 먼저 실행해야 명령을 쓸 수
> 있습니다(또는 `.venv/bin/bandprepare` 처럼 전체 경로 사용).

### ⚠️ 명령 이름 — 소스 설치 vs 포터블 번들 (역전 주의)

같은 이름 `bandprepare` 가 설치 방식에 따라 **다른 프로그램**을 가리킵니다:

| 실행 방식 | CLI 명령 | GUI 명령 |
|-----------|----------|----------|
| **소스/pip 설치** (이 문서) | `bandprepare` | `bandprepare-gui` |
| **포터블 번들** (릴리스 다운로드) | `bandprepare-cli` | `bandprepare` (더블클릭) |

- 즉 **소스 설치에서 `bandprepare` 는 CLI**, GUI는 `bandprepare-gui` 입니다.
  (`pyproject.toml [project.scripts]` 정의.)
- 반대로 포터블 번들에서 접미사 없는 `bandprepare` 는 **GUI**이고 CLI는 `bandprepare-cli`
  입니다(번들은 GUI를 더블클릭 진입점으로 두기 때문 — `bandprepare.spec`).
- 사용자 가이드([CLI](CLI.md)/[GUI](GUI.md))의 명령 예시는 **포터블 번들 기준**입니다.

### 선택 extra (필요할 때만)

```bash
uv pip install -e ".[gui]"        # 데스크톱 GUI(PySide6) → bandprepare-gui
uv pip install -e ".[roformer]"   # RoFormer 모델(bs_roformer / mel_band_roformer)
uv pip install -e ".[build]"      # 포터블 번들 빌드용 PyInstaller
uv pip install -e ".[dev]"        # 테스트용 pytest
# 한 번에: uv pip install -e ".[gui,roformer,build,dev]"
```

- **포터블 앱에는 GUI·RoFormer가 이미 포함**되어 있으므로, 위 extra는 *소스 설치에서만*
  필요합니다.
- `.[roformer]` 가 설치하는 것은 `rotary-embedding-torch`, `beartype`, `einops` **뿐**입니다.
  Mel-Band RoFormer의 유일한 librosa 사용(`filters.mel`)을 순수 NumPy로 벤더링해
  `librosa`/`numba`/`llvmlite` 는 더 이상 필요 없습니다(설계: [ARCHITECTURE.md](../ARCHITECTURE.md) §12 D6).

> 아키텍처와 설계 배경(특히 호환성 때문에 audio-separator를 쓰지 않은 이유)은
> [ARCHITECTURE.md](../ARCHITECTURE.md) 를 참고하세요.

## GPU 가속 (CUDA) — 소스 설치

포터블 앱의 **Linux/Windows 번들은 CPU 전용 torch**라 CUDA 가속을 쓸 수 없습니다(용량을
작게 유지하려는 의도). NVIDIA GPU로 몇 배 빠르게 돌리려면 **소스에서 CUDA 빌드 torch를
직접 설치**하세요. NVIDIA 드라이버가 미리 설치돼 있어야 합니다.

```bash
# 1) CUDA 빌드 torch 설치 (드라이버에 맞는 CUDA 버전 선택 — 예: cu121 = CUDA 12.1)
pip install "torch>=2.1.0,<2.3.0" "torchaudio>=2.1.0,<2.3.0" \
  --index-url https://download.pytorch.org/whl/cu121

# 2) BandPrepare 설치 (이미 만족된 torch는 건드리지 않음)
pip install -e .

# 3) GPU로 실행 (소스 설치에선 CLI 명령이 bandprepare)
bandprepare 내곡.mp3 --device cuda
```

> 💡 **macOS**는 CUDA가 없습니다. Apple Silicon은 `--device mps` 로 GPU(Metal)를 씁니다
> (포터블 macOS 앱도 동일). Intel Mac은 MPS가 느려 `auto` 가 일부러 CPU를 선택합니다.
> CUDA는 **Linux / Windows + NVIDIA GPU** 전용입니다.

## 개발 / Development

```bash
uv pip install -e ".[dev]"
pytest -q                      # 모델 없이 도는 빠른 단위 테스트
```

`pytest` 단위 테스트는 모델 가중치 없이 도는 빠른 테스트만 포함합니다(인자 파싱,
출력 경로 계획, 장치 해석, 샘플 생성, ffmpeg 해석, 진행률 콜백, GUI 옵션 구성 등).
GUI 테스트는 디스플레이가 없어도 되도록 오프스크린으로 돕니다:

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

실제 분리는 [레퍼런스의 "동작 확인"](REFERENCE.md#동작-확인-샘플-실행--verified-run) 절차로 수행합니다.

## 포터블 앱 빌드 (PyInstaller)

ffmpeg·Python·torch를 따로 설치하지 않고 **더블클릭으로 실행**하는 포터블 번들을 만들 수
있습니다(torch가 네이티브라 단일 범용 바이너리는 불가 → **플랫폼별로 따로 빌드**).

```bash
uv pip install -e ".[gui,build]"          # PySide6 + pyinstaller
pyinstaller --noconfirm bandprepare.spec  # → dist/bandprepare/  (~1.4 GB)
                                          #   macOS는 dist/BandPrepare.app 도 함께 생성
./dist/bandprepare/bandprepare            # 실행 (GUI)
./dist/bandprepare/bandprepare-cli 내곡.mp3   # 실행 (CLI)
```

- 한 번들에 **GUI(`bandprepare`)와 CLI(`bandprepare-cli`) 두 바이너리**가 함께 들어갑니다.
  같은 라이브러리(torch 등)를 공유하므로 CLI를 추가해도 용량은 거의 늘지 않습니다. Python
  설치 없이 `./dist/bandprepare/bandprepare-cli <곡>` 로 CLI를 쓸 수 있습니다(옵션은 동일).
- **앱 아이콘**: 원본은 `assets/icon.svg` 하나입니다. 수정 후
  `QT_QPA_PLATFORM=offscreen python packaging/make_icons.py` 를 실행하면 빌드가 쓰는
  세 파일 — `assets/icon.icns`(macOS 번들), `assets/icon.ico`(Windows exe),
  `src/bandprepare/gui/icon.png`(창/태스크바) — 이 다시 생성됩니다. 셋 다 커밋 대상이며,
  `.icns` 는 macOS의 `iconutil` 이 필요해 macOS에서만 재생성됩니다.
- **ffmpeg는 번들에 동봉**(`imageio-ffmpeg`)되어 시스템 설치가 필요 없습니다.
- **모델 가중치만** 첫 실행 시 캐시(`~/.cache/bandprepare`, 번들 바깥)로 다운로드됩니다.
- **RoFormer 모델(BS-RoFormer · Mel-Band)도 번들에 동봉**됩니다. Mel-Band의 유일한
  librosa 사용을 순수 numpy로 벤더링해 numba/llvmlite 없이 동결됩니다(설계: [ARCHITECTURE.md](../ARCHITECTURE.md) §12 D6).
- 번들이 잘 묶였는지 디스플레이 없이 점검:
  `BANDPREPARE_GUI_SELFTEST=1 QT_QPA_PLATFORM=offscreen ./dist/bandprepare/bandprepare`
- **macOS**: 같은 빌드가 onedir와 함께 **`dist/BandPrepare.app`**(windowed GUI 번들)도 만듭니다.
  `open dist/BandPrepare.app`(또는 더블클릭)하면 **터미널 없이** 창이 바로 뜹니다(spec의 `BUNDLE`,
  `sys.platform == "darwin"` 한정). CI는 macOS에서 이 `.app`을 릴리스 자산으로 패키징하고
  (Linux·Windows는 onedir 폴더), CLI는 `.app/Contents/MacOS/bandprepare-cli` 에 함께 들어갑니다.
- 멀티플랫폼 빌드 매트릭스는 `.github/workflows/build.yml`. macOS `.app`·바이너리는 PyInstaller가
  **ad-hoc 서명**(무료, 인증서 불필요)해 실행은 되지만, Gatekeeper의 "확인되지 않은 개발자" 경고를
  없애려면 **유료 Developer ID 서명 + 공증(notarize)** 이 필요합니다(미적용 — 아래 "다운로드한 릴리스
  첫 실행" 참고). 배포·패키징 설계 결정은 [ARCHITECTURE.md](../ARCHITECTURE.md) §12 참고.

## 다운로드한 릴리스 첫 실행 (서명 경고 우회)

GitHub Releases에서 받은 번들은 **정식 서명/공증이 안 돼 있어**(ad-hoc 서명까지만) 첫 실행 시
OS 경고가 뜹니다. 실행 자체는 가능하며, 한 번만 아래로 허용하면 됩니다(다음 실행부터는 경고 없음).

- **macOS** (`BandPrepare.app`): 다운로드 격리 + "확인되지 않은 개발자" 때문에 막힙니다.
  **앱을 우클릭 → 열기 → 열기** 하면 됩니다 — `.app` 은 ad-hoc 서명된 **단일 번들**이라 이 한 번의
  허용으로 내부 라이브러리까지 전부 풀립니다. 터미널을 선호하면:
  ```bash
  xattr -dr com.apple.quarantine BandPrepare.app
  ```
  > ℹ️ 예전 onedir **폴더** 번들은 폴더 안 수백 개의 `.dylib`가 각각 격리돼, 시스템 설정의
  > **"확인 없이 열기"**(더블클릭한 파일 하나만 허용)로는 `library load disallowed by system
  > policy` 가 안 풀리고 `xattr -dr`(재귀)가 필요했습니다. windowed `.app` 으로 바꾼 뒤로는
  > 우클릭 → 열기 한 번이면 번들 전체가 풀립니다.
- **Windows**: SmartScreen "Windows의 PC 보호" 화면 → **추가 정보 → 실행**. (일부 백신이
  PyInstaller 바이너리를 오탐할 수 있으니 신뢰 목록에 추가.)
- **Linux**: 경고 없음. 필요 시 `chmod +x ./bandprepare/bandprepare` 후 실행.

## 구조

자세한 설계·데이터 흐름·설계 결정(특히 호환성 때문에 audio-separator 미사용)은
[ARCHITECTURE.md](../ARCHITECTURE.md) 참고.

```
src/bandprepare/
├── cli.py                 # 인자 파싱 / 진입점 (CLI)
├── pipeline.py            # 단계 오케스트레이션 (+ 진행률 콜백)
├── audio.py               # 입출력 / ffmpeg 해석(시스템·동봉) / 디코딩
├── device.py              # --device 해석
├── gui/                   # 데스크톱 GUI (PySide6) — bandprepare-gui
│   ├── app.py             # 메인 윈도우 + build_options + main()
│   └── worker.py          # QThread 워커 (pipeline.run 호출)
├── separation/
│   ├── base.py            # Separator 프로토콜 + ModelInfo
│   ├── registry.py        # 모델 카탈로그(--stem-model/--drum-model/--list-models)
│   ├── download.py        # 가중치 다운로드/캐시 공용 헬퍼
│   ├── stems.py           # Demucs 백엔드 (htdemucs_6s/htdemucs_ft)
│   ├── roformer.py        # RoFormer 백엔드 (bs_roformer/mel_band_roformer) + 공용 _demix
│   ├── mdx23c.py          # MDX23C DrumSep 백엔드 (roformer._demix 재사용)
│   ├── drums.py           # LarsNet 백엔드
│   └── drumsep.py         # DrumSep(inagoy) 백엔드
└── vendor/
    ├── larsnet/           # 벤더링된 LarsNet 모델 코드
    ├── mdx23c/            # 벤더링된 TFC-TDF v3 (ZFTurbo v1.0.12, MIT)
    └── roformer/          # 벤더링된 BS/Mel-Band RoFormer (ZFTurbo v1.0.12, MIT)

packaging/bandprepare_gui.py   # PyInstaller 진입 런처
bandprepare.spec               # PyInstaller 포터블 번들 빌드 스펙
```

---

> 🖥 사용법 → [CLI 가이드](CLI.md) · 📚 레퍼런스 → [REFERENCE.md](REFERENCE.md) · 🏗 설계 → [ARCHITECTURE.md](../ARCHITECTURE.md)
