# BandPrepare — 개발 / 빌드 / 릴리스 가이드

개발 환경 셋업, 테스트, 포터블 앱 빌드(PyInstaller), 다운로드한 릴리스의 첫 실행
(서명 경고 우회), 소스 트리 구조를 다룹니다. 내부 설계·데이터 흐름·설계 결정은
[ARCHITECTURE.md](../ARCHITECTURE.md)를 참고하세요.

> Dev setup, tests, portable-app build (PyInstaller), first-run signing-warning
> workarounds, and source layout. For internal design see
> [ARCHITECTURE.md](../ARCHITECTURE.md).

---

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
./dist/bandprepare/bandprepare            # 실행 (GUI)
./dist/bandprepare/bandprepare-cli 내곡.mp3   # 실행 (CLI)
```

- 한 번들에 **GUI(`bandprepare`)와 CLI(`bandprepare-cli`) 두 바이너리**가 함께 들어갑니다.
  같은 라이브러리(torch 등)를 공유하므로 CLI를 추가해도 용량은 거의 늘지 않습니다. Python
  설치 없이 `./dist/bandprepare/bandprepare-cli <곡>` 로 CLI를 쓸 수 있습니다(옵션은 동일).
- **ffmpeg는 번들에 동봉**(`imageio-ffmpeg`)되어 시스템 설치가 필요 없습니다.
- **모델 가중치만** 첫 실행 시 캐시(`~/.cache/bandprepare`, 번들 바깥)로 다운로드됩니다.
- **RoFormer 모델(BS-RoFormer · Mel-Band)도 번들에 동봉**됩니다. Mel-Band의 유일한
  librosa 사용을 순수 numpy로 벤더링해 numba/llvmlite 없이 동결됩니다(설계: [ARCHITECTURE.md](../ARCHITECTURE.md) §12 D6).
- 번들이 잘 묶였는지 디스플레이 없이 점검:
  `BANDPREPARE_GUI_SELFTEST=1 QT_QPA_PLATFORM=offscreen ./dist/bandprepare/bandprepare`
- 멀티플랫폼 빌드 매트릭스는 `.github/workflows/build.yml`. 코드 서명/공증은 유료 인증서가
  필요해 미적용 상태입니다(아래 "다운로드한 릴리스 첫 실행" 참고). 배포·패키징 설계 결정은
  [ARCHITECTURE.md](../ARCHITECTURE.md) §12 참고.

## 다운로드한 릴리스 첫 실행 (서명 경고 우회)

GitHub Releases에서 받은 번들은 **코드서명이 안 돼 있어** 첫 실행 시 OS 경고가 뜹니다.
실행 자체는 가능하며, 한 번만 아래로 허용하면 됩니다(다음 실행부터는 경고 없음).

- **macOS**: 다운로드 격리 때문에 막힙니다. 터미널에서 **격리 속성을 재귀로 제거**하세요:
  ```bash
  xattr -dr com.apple.quarantine /받은경로/bandprepare
  ```
  > ⚠️ `_internal/Python` 같은 **하위 라이브러리 로드 차단**(`library load disallowed by
  > system policy`) 에러는 시스템 설정의 **"확인 없이 열기"** 만으론 안 풀립니다 — 그 버튼은
  > 더블클릭한 파일 하나만 허용하고, 폴더 안 수백 개의 `.dylib`는 그대로 격리되기 때문입니다.
  > 위 `xattr -dr`(재귀)로 폴더 전체를 한 번에 풀어야 확실합니다.
- **Windows**: SmartScreen "Windows의 PC 보호" 화면 → **추가 정보 → 실행**. (일부 백신이
  PyInstaller 바이너리를 오탐할 수 있으니 신뢰 목록에 추가.)
- **Linux**: 경고 없음. 필요 시 `chmod +x ./bandprepare` 후 실행.

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
