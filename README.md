# BandPrepare 🥁🎸

음원 한 곡을 **악기별 트랙**으로 분리하고, **드럼은 다시 킥/스네어/하이햇/심벌/톰**으로
세분화해 주는 도구입니다. 밴드 멤버가 곡을 파트별로 나눠 개별 연습
(내 파트만 듣기 / 내 파트만 빼고 듣기)에 쓰는 것을 목표로 합니다.
**커맨드라인(CLI)** 과 **마우스로 쓰는 GUI** 를 모두 제공합니다.

> A tool that splits a song into per-instrument stems and further splits the drum
> stem into individual kit pieces, so band members can practice their part in
> isolation. Available as both a CLI and a desktop GUI.
> (문서는 한국어 사용 가이드 중심입니다.)

---

## ⚡ 한눈에 (TL;DR)

**설치 없이** 포터블 앱을 받아 바로 씁니다 — Python·ffmpeg·torch·RoFormer 모델이 모두 들어 있습니다.

1. [Releases](../../releases)에서 내 OS에 맞는 파일을 받습니다.
   `macos-arm64`(애플 실리콘) · `macos-x86_64`(인텔 맥) · `linux-x86_64` · `windows-x86_64`
2. 압축을 풀면 **`bandprepare/` 폴더 하나**가 나옵니다(안에 실행 파일 2개).
3. 🖱 **마우스로**: `bandprepare` 를 **더블클릭** → [GUI 가이드](docs/GUI.md)
   🖥 **터미널로**: `./bandprepare/bandprepare-cli 내곡.mp3` → [CLI 가이드](docs/CLI.md)

결과는 `./output/내곡/` 폴더에 생깁니다.

> ⚠️ 받은 앱은 코드서명이 안 돼 있어 **첫 실행 때 OS 경고**가 한 번 뜹니다(허용하면 다음부터는 없음).
> macOS는 `xattr -dr com.apple.quarantine <받은폴더>/bandprepare` 가 필요합니다 —
> 우회법은 각 가이드와 [개발 가이드](docs/DEVELOPMENT.md#다운로드한-릴리스-첫-실행-서명-경고-우회)에 있습니다.
> 첫 실행에는 모델 가중치를 받느라 인터넷이 필요합니다(이후 캐시됨).

> 🛠 릴리스가 아직 비공개(draft)이거나 **소스에서 직접 빌드·설치**하고 싶다면
> → [개발 가이드](docs/DEVELOPMENT.md).

---

## 📂 용도별 문서

| 이런 분께 | 문서 |
|-----------|------|
| 🖥 **터미널로 쓰는 분** — 포터블 CLI(`bandprepare-cli`) 받기 · 첫 실행 · 연습 레시피 · FAQ | [docs/CLI.md](docs/CLI.md) |
| 🖱 **마우스로 쓰는 분** — 포터블 앱(`bandprepare`) 더블클릭 · 드래그 앤 드롭 | [docs/GUI.md](docs/GUI.md) |
| 📚 **레퍼런스** — 의존성 · 옵션 전체 · 파이프라인 · 출력 구조 · 라이선스 · 한계 · 성능 · 종료 코드 | [docs/REFERENCE.md](docs/REFERENCE.md) |
| 🛠 **개발자** — 소스 설치 · 빌드 · 테스트 · 포터블 앱 빌드 · GPU(CUDA) · 서명 경고 우회 | [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) |
| 🏗 **내부 구조 · 설계 결정** | [ARCHITECTURE.md](ARCHITECTURE.md) |

---

## ⚖️ 라이선스 요약

BandPrepare 코드와 대부분의 모델(Demucs / DrumSep / MDX23C / RoFormer)은 MIT 등 상업
이용이 가능한 라이선스입니다. 다만 **드럼 세부 분리 기본 모델 LarsNet의 사전학습
체크포인트는 CC BY-NC 4.0(비상업)** 이라, 그 가중치를 쓴 결과물의 상업적 이용은
제한됩니다. 상업적 용도라면 `--no-drum-split`(1단계 Demucs만) 또는
`--drum-model drumsep` / `mdx23c`(둘 다 MIT)를 쓰세요. 모델별 출처·라이선스 전체는
[docs/REFERENCE.md](docs/REFERENCE.md#모델-출처--라이선스--model-sources--licenses)를 참고하세요.
