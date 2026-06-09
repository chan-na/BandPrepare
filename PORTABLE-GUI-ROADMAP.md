# 포터블 배포 + GUI 로드맵 / Portable distribution + GUI roadmap

BandPrepare를 **사용자가 어떤 의존성도 따로 설치하지 않는 포터블 데스크톱 앱**으로
만들고, 최종적으로 **PySide6(Qt) GUI**를 붙이는 작업의 다중 세션용 로드맵입니다.

> **이 문서 사용법**: 매 세션 시작 시 아래 "현재 상태 / 다음 액션"을 먼저 읽고,
> 작업 후 체크박스(`[ ]`→`[x]`)와 상태 줄을 갱신해 커밋하세요. 각 Phase의
> "완료 기준"을 만족해야 다음으로 넘어갑니다.

---

## 🧭 현재 상태 / 다음 액션  ← 매 세션 여기부터

- **현재 Phase**: Phase 0~4 완료 ✅ — **Phase 5 CI 4종 전부 그린**. 호스티드 러너로
  linux-x86_64 · macos-arm64 · windows-x86_64 빌드+동결 self-test 통과, **macos-x86_64(Intel)은
  self-hosted 러너(이 Intel iMac)**에서 빌드+동결 self-test 통과(별도 `build-macos-intel`
  잡, 태그/수동 게이팅). `v*` 태그 시 4종 모두 draft GitHub Release에 자동 첨부.
- **RoFormer 5a·5b 완료** ✅: BS-RoFormer + Mel-Band 둘 다 동봉(동결 self-test
  `roformer_bs=ok roformer_mel=ok`, 번들에 numba/llvmlite/librosa 없음). Mel-Band의
  유일한 librosa 사용(`filters.mel`)을 순수 numpy로 벤더링(`vendor/roformer/_mel.py`)해
  librosa/numba/llvmlite를 그래프에서 통째로 제거 → **D6 블로커 영구 해소**.
- **다음 액션**: torch CPU 휠 전환(Linux/Win 번들 크기↓) → macOS·Win 코드서명(유료 인증서 필요).
- **PoC 빌드 플랫폼**: Intel mac x86_64 (Python 3.11, torch 2.2.2, PySide6 6.11.1).
  동결 번들 self-test 통과(시스템 ffmpeg/torch 없이 동작 입증).
- **블로커/메모**: 실 모델 분리 end-to-end는 디스플레이+가중치 필요 → 수동 검증 권장.
  코드서명·공증은 유료 인증서가 있어야 진행 가능.

---

## 1. 목표 / 요구사항 (확정)

- **포터블의 정의**: "외부 의존성 다운로드가 없을 것". 사용자는 ffmpeg·Python·pip
  패키지를 따로 설치하지 않는다. **모델 가중치만** 첫 실행 시 다운로드해도 됨(허용).
- **최종 산출물**: PySide6 기반 **GUI 데스크톱 앱**. 비전문가 밴드 멤버가 더블클릭으로 실행.
- **CLI는 유지**: GUI는 기존 CLI와 같은 코어를 공유하는 얇은 층으로 추가.

## 2. 확정된 결정 (Decision log)

| # | 결정 | 사유 |
|---|------|------|
| D1 | 배포 = **PyInstaller one-folder** 플랫폼별 번들 | torch+인터프리터는 네이티브라 단일 범용 바이너리 불가. one-file은 매 실행 ~2GB temp 해제로 느림 |
| D2 | **Docker / uv-부트스트랩 탈락** | Docker는 비전문가 GUI 부적합; uv는 설치 시 deps 다운로드 → "외부 의존성 다운로드 없음" 위배 |
| D3 | GUI = **PySide6 (Qt)** | 진짜 네이티브 앱, torch 번들 검증됨. (대안 Gradio+pywebview는 MVP용) |
| D4 | ffmpeg = **`imageio-ffmpeg` 동봉** | 정적 ffmpeg를 pip로 동봉(LGPL). 사용자 `brew install` 제거 |
| D5 | 모델은 **런타임 다운로드 유지** | 번들 ~2GB 절감. 캐시는 번들 바깥(`BANDPREPARE_CACHE`→`XDG_CACHE_HOME`→`~/.cache`)이라 frozen 앱에서 정상 작동 |
| D6 | ~~초기 번들은 **RoFormer 제외**~~ → **해소(5a/5b)** | `numba/llvmlite` 런타임 JIT라 PyInstaller 동봉이 까다로움 → 초기엔 Demucs+LarsNet/DrumSep/MDX23C만. Phase 5a에서 BS-RoFormer(numba 무관) 동봉, 5b에서 Mel-Band의 `librosa.filters.mel`을 순수 numpy로 벤더링(`vendor/roformer/_mel.py`)해 librosa/numba/llvmlite를 제거 → **양쪽 모두 동봉, 블로커 영구 해소** |
| D7 | **플랫폼별 빌드 필수** | torch<2.3(Intel-mac 휠 마지막 2.2.2) 등으로 mac x86_64 / mac arm64 / Linux / Win 각각 빌드 |
| D8 | 같은 onedir 번들에 **CLI 바이너리(`bandprepare-cli`) 동봉** | GUI/CLI 두 EXE가 한 COLLECT의 라이브러리(torch 등) 공유 → CLI 추가 비용은 자기 PYZ+부트스트랩뿐. Python 없이 `bandprepare-cli <곡>` 실행 |

## 3. 설계 원칙 — 코어/GUI 분리

```
GUI 층 (gui/, QThread 워커)  ─┐
CLI 층 (cli.py)              ─┼─→  pipeline.run(Options)  ← 코어는 그대로
                              ┘     (separation/, audio.py …)
```

- 코어(`pipeline.run(Options)`)는 이미 CLI와 분리돼 있음 = 큰 자산. **건드리지 않는다**.
- GUI는 코어를 호출하는 얇은 층. 분리는 **QThread 워커**에서 실행(메인 스레드 블록 방지).
- 진행률은 콜백으로 코어 → UI 전달.

---

## 4. Phase 체크리스트

### Phase 0 — 계획 / 저장소 준비  ✅
- [x] 배포 방식·GUI 프레임워크 결정 (위 Decision log)
- [x] 로드맵 문서화 (이 파일)
- [x] `.gitignore`에 빌드 산출물 추가(`build/`, `dist/`). `*.spec`은 추적 유지(소스 파일)

### Phase 1 — ffmpeg 동봉 (작고 즉시 검증 가능)  ✅
- [x] `pyproject.toml` 의존성에 `imageio-ffmpeg` 추가
- [x] 앱 시작 시 동봉 ffmpeg를 `PATH`에 노출하는 헬퍼 `prepare_ffmpeg_path()` 추가
      (CLI 진입 `cli.main`에서 호출, GUI도 공유 예정).
- [x] `audio.py`의 `ensure_ffmpeg()`/`ffmpeg_available()`가 동봉 ffmpeg도 인식
      (`resolve_ffmpeg()` = system PATH → 번들 순).
- **주의(중요)**: `imageio-ffmpeg`는 **ffmpeg만** 동봉(ffprobe 없음)하고 바이너리 이름이
  버전 접미사(`ffmpeg-macos-x86_64-v7.1`)라 단순 PATH 주입으론 demucs `AudioFile`이
  못 씀(ffprobe 필요). → 압축 입력은 `load_track`이 **ffmpeg만으로 직접 디코딩**
  (`_decode_with_ffmpeg`, f32le PCM, ffprobe 불필요)하는 경로를 추가. demucs 경로는
  시스템 풀 ffmpeg가 있을 때만 1순위로 사용.
- **완료 기준**: ✅ 시스템 ffmpeg/ffprobe가 PATH에 **없는 상태**에서 mp3 디코딩 성공
  (`test_load_track_decodes_mp3_via_bundled_ffmpeg`로 자동 검증).

### Phase 2 — 코어에 진행률 콜백  ✅
- [x] `pipeline.Options`에 `progress_callback`(타입 별칭 `ProgressCallback =
      Callable[[stage:str, fraction:float|None, msg:str], None]`) 추가
- [x] `pipeline.run`이 단계 경계에서 `emit()` 호출:
      `start → stem_model → load_audio → separate_stems → (save…) → stems_done →
      [minus] → drum_model → separate_drums → (save…) → drums_done → done`
      (드럼 분리 없으면 stem 단계만, 마지막 `done` fraction=1.0)
- [x] CLI는 콜백 미설정(None) → `emit()`은 no-op, 기존 tqdm 유지 — 회귀 테스트로 확인
- **완료 기준**: ✅ 콜백을 넘기면 단계 전환이 순서대로 보고됨(`test_progress_callback_*`).
- **메모**: 모델 내부 세부 진행률은 MVP 범위 밖(fraction은 단계 경계 추정치, 스피너로 충분).
  추후 demucs/larsnet tqdm 후킹 검토.

### Phase 3 — PySide6 GUI (얇은 층)  ✅
- [x] `pyproject.toml`에 `gui` extra(`PySide6>=6.5`) + `bandprepare-gui` 스크립트 엔트리 추가
- [x] `src/bandprepare/gui/` 생성 (`app.py`=윈도우+`build_options`+`main`,
      `worker.py`=QThread 워커, `__init__.py`/`__main__.py` 엔트리)
  - [x] 입력 파일 드래그앤드롭 + 파일 선택 (선택 시 출력 폴더 자동 채움)
  - [x] 모델 드롭다운 — `registry`의 `STEM_MODELS`/`DRUM_MODELS`에서 **동적 생성**
  - [x] 스템 체크박스 / `--minus` 체크박스 / 포맷 / 장치 / 출력 폴더 선택
        (스템 모델에 `drums` 없으면 드럼 관련 컨트롤 자동 비활성화 — 예: mel_band_roformer)
  - [x] 실행 버튼 → **QThread 워커**가 `pipeline.run(Options)` 호출 (시그널로만 교신)
  - [x] 진행바 + 로그 패널(Phase 2 콜백을 `progress` 시그널로 연결, fraction→bar)
  - [x] 완료 후 "출력 폴더 열기" 버튼 (`QDesktopServices`)
- **검증**: PySide6 6.11.1을 Intel mac x86_64에서 설치/오프스크린 구동 확인. GUI 단위
  테스트 4종(`build_options` 매핑, 모델 전환 시 컨트롤 토글, 위젯 수집, 입력 필수) 통과.
  실제 분리 실행은 디스플레이/모델 가중치 필요 → Phase 4 번들 검증과 함께 수동 확인 예정.
- **완료 기준**: GUI 구성·옵션 수집·워커 연결·진행 표시까지 동작(오프스크린 검증). 실
  분리 end-to-end는 디스플레이 환경에서 수동 확인.

### Phase 4 — PyInstaller 패키징 PoC (★ Phase 1 직후 권장)  ✅
- [x] `bandprepare.spec` 작성: one-folder(onedir), 엔트리=GUI(`packaging/bandprepare_gui.py`)
  - `collect_all`: torch, torchaudio, demucs, soundfile, imageio_ffmpeg, PySide6
  - vendor YAML config(`vendor/**/configs/*.yaml`)를 런타임 경로(`bandprepare/vendor/...`)에 `datas`로 동봉
  - hidden imports: bandprepare 백엔드(지연 임포트라 명시) + julius/lameenc/dora/yaml
  - excludes: ~~RoFormer 모델/deps 전체~~ → Phase 5a/5b에서 BS-RoFormer·Mel-Band 모두
    hiddenimports로 이동(동봉). 현재 excludes의 `numba/llvmlite/librosa`는 **실제로 그래프에
    없음**(Mel-Band가 `vendor/roformer/_mel.py` 순수 numpy 사용) — 혹시 모를 전이 임포트
    재유입을 막는 belt-and-braces 가드로만 유지. `separation.roformer` 모듈 자체는 MDX23C가
    `_demix`를 재사용하므로 **포함**(모듈 상단은 경량, 무거운 vendor 모델은 지연 임포트)
  - `pyinstaller`는 `build` extra로 추가
- [x] 현재 플랫폼(Intel mac x86_64)에서 빌드 — 산출물 `dist/bandprepare/` (~1.4GB)
- **검증(자동, 디스플레이/모델 불필요)**: GUI `main()`에 `BANDPREPARE_GUI_SELFTEST=1` 훅
  추가 → 동결 번들을 **시스템 ffmpeg를 PATH에서 제거**하고 오프스크린 실행:
  - torch/torchaudio/demucs/soundfile/imageio_ffmpeg/numpy/yaml 임포트 OK (시스템 Python/torch 불필요)
  - `MainWindow` 구성 OK, registry 4 stem / 3 drum 모델
  - **동봉 ffmpeg 해석 OK** → 셸 심링크가 `_internal/.../ffmpeg-macos-x86_64-v7.1`을 가리키고
    `ffmpeg -version` 실행됨 (압축 입력 디코딩 경로 동작 입증)
  - MDX23C 번들 config 읽기 OK, 캐시(`~/.cache/bandprepare`, 번들 바깥)에 쓰기 OK → exit 0
- **완료 기준**: ✅ 패키징 고유 리스크(임포트/데이터/ffmpeg/캐시) 동결 상태에서 통과.
  실제 모델 다운로드+분리 end-to-end(≈2GB·CPU 수분, 코어 코드는 이미 테스트됨)는 디스플레이
  환경에서 수동 확인 권장.
- **알려진 한계(PoC)**: ~~RoFormer 스템 모델이 선택 시 degrade~~ → Phase 5a/5b에서
  **BS-RoFormer + Mel-Band 동봉 완료**(둘 다 번들에서 동작). degrade 경로 해소.

### Phase 5 — 멀티플랫폼 / 릴리스 ✅ / RoFormer ✅ / 서명 ◐
- [x] GitHub Actions 빌드 **4종 전부 그린** (`.github/workflows/build.yml`):
      각 OS에서 테스트 → `pyinstaller bandprepare.spec` 빌드 → **동결 self-test** →
      아티팩트 업로드. universal2 대신 arch별 별도 빌드(D7, torch가 macOS universal2 휠
      미제공). Linux는 Qt 런타임 libs(apt) 설치 스텝 포함.
      첫 실행에서 Windows만 실패했는데 코어가 아니라 테스트(`prepare_ffmpeg_path`가 Windows에서
      `ffmpeg.exe`/PATHEXT 케이싱 `ffmpeg.EXE` 반환)였고 `2ab50a8`에서 수정.
- [x] **Intel mac은 self-hosted 러너로 자동화**: GitHub 호스티드 macos-13 러너가 불안정
      (큐 50분+)이라, Intel iMac에 self-hosted 러너(launchd 로그인 서비스)를 등록하고
      별도 `build-macos-intel` 잡에서 빌드. **태그/`workflow_dispatch`에서만** 동작하게
      게이팅 → 퍼블릭 저장소의 fork-PR 코드가 개인 머신에서 실행되는 것을 차단.
      self-hosted 함정 2개: ⓐ `actions/setup-python`의 macOS 빌드는 prefix
      `/Users/runner/hostedtoolcache`가 박혀 있어 실패 → **uv**로 Python 3.11 provision.
      ⓑ runsvc.sh가 `.env`를 안 읽음. 자세한 운영 메모는 세션 메모리 참조.
- [x] **배포 채널 — GitHub Releases (태그 푸시 시 자동 첨부)**: `softprops/action-gh-release`로
      각 잡이 번들을 아카이브(Unix tar.gz / Win zip)해 **draft** Release에 첨부. Intel도
      self-hosted 잡이 자동 첨부 → 수동 업로드 불필요. `git tag v0.1.0 && git push origin v0.1.0`
      후 draft 검토→publish.
- [ ] torch **CPU 휠로 전환**(`--index-url .../whl/cpu`, Linux/Windows만) — 현재 기본 PyPI가
      CUDA 휠을 받아 번들/CI가 무거움. 크기·시간 최적화(워크플로에 주석 안내 있음).
- [ ] macOS 코드사인 + 공증 / Windows 코드사인 — **유료 인증서 필요**(워크플로에 주석
      플레이스홀더만). 미서명 시 Gatekeeper/SmartScreen 첫 실행 경고(R2).
- [x] **RoFormer 5a — BS-RoFormer 동봉**: numba 무관 경로. spec excludes에서 BS 모델/deps
      (`vendor.roformer.bs_roformer`/`.attend`, rotary-embedding-torch/beartype/einops) 제거 →
      hiddenimports로 이동, CI에 `roformer` extra 추가, 동결 self-test가 BS 모델 import+
      `build_model('bs_roformer', …)` 인스턴스화(131.7M params)를 검증(`roformer_bs=ok`).
      번들에 numba/llvmlite/librosa **없음** 확인.
- [x] **RoFormer 5b — Mel-Band 동봉**: `mel_band_roformer.py`의 유일한 librosa 사용
      (`filters.mel`)을 순수 numpy로 `vendor/roformer/_mel.py`에 벤더링(librosa 0.11.0 기준,
      `tests/test_mel_filter.py`가 `np.allclose(atol=0)`로 동등성 고정) → `from librosa import
      filters` 제거, pyproject `roformer` extra·spec excludes에서 librosa/numba/llvmlite 제거,
      hiddenimports에 `mel_band_roformer` 추가. 동결 self-test가 Mel-Band import+
      `build_model('mel_band_roformer', …)` 인스턴스화(228.2M params)를 검증(`roformer_mel=ok`).
      번들에 numba/llvmlite/librosa **없음** 재확인 → **D6 블로커 영구 해소**.

> 남은 Phase 5 항목(코드서명)은 외부 의존(유료 인증서)이 남아 별도 진행. CI 빌드/릴리스
> 자동화와 RoFormer 동봉(5a·5b)은 완료.

---

## 5. 리스크 & 오픈 이슈

- **R1 torch 번들 누락 임포트**: PyInstaller가 torch 동적 라이브러리/플러그인을 놓칠 수
  있음 → `--collect-all`/hook으로 대응, Phase 4에서 조기 검증.
- **R2 macOS Gatekeeper / Windows SmartScreen**: 서명·공증 안 하면 첫 실행 경고.
  비전문가 대상이면 결국 인증서 필요(Phase 5).
- **R3 번들 크기**: torch 포함 ~1.5–3GB/플랫폼. 압축·배포 채널 고려.
- **R4 mac universal2**: torch 때문에 단일 universal 빌드 까다로움 → arch별 별도 빌드.
- **R5 캐시 쓰기 권한**: frozen 앱이 `~/.cache/bandprepare`에 쓸 수 있는지 확인
  (현재 설계상 OK, Phase 4에서 실증).

## 6. 참고 (코드 touch points)

- ffmpeg 해석: `src/bandprepare/audio.py` — `ffmpeg_available()`(L23), `ensure_ffmpeg()`(L27),
  `AudioFile(...).read(...)`(L65, demucs가 ffmpeg 셸 호출)
- 파이프라인 코어: `src/bandprepare/pipeline.py` — `Options`, `run`, `planned_outputs`
- 모델 카탈로그(드롭다운 소스): `src/bandprepare/separation/registry.py` —
  `STEM_MODELS`/`DRUM_MODELS`, `format_table()`
- 캐시 경로: `src/bandprepare/separation/download.py` — `model_cache_dir()`
- 설계 배경 전반: [ARCHITECTURE.md](ARCHITECTURE.md)
