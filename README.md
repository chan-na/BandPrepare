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

```bash
# 1) 설치 (최초 1회)
uv venv --python 3.11 .venv && source .venv/bin/activate && uv pip install -e .

# 2) 곡 분리
bandprepare 내곡.mp3

# 3) 결과는 ./output/내곡/ 폴더에 생김
```

> 🖱 **터미널이 어렵다면?** 마우스로 쓰는 **GUI**도 있습니다 → [GUI 가이드](docs/GUI.md).
> 설치 없이 더블클릭으로 쓰는 **포터블 앱**은 [Releases](../../releases)에서 받으세요.

---

## 📂 용도별 문서

| 이런 분께 | 문서 |
|-----------|------|
| 🖥 **터미널로 쓰는 분** — 설치 · 첫 실행 · 연습 레시피 · GPU 가속 · FAQ | [docs/CLI.md](docs/CLI.md) |
| 🖱 **마우스로 쓰는 분** — 드래그 앤 드롭 데스크톱 GUI | [docs/GUI.md](docs/GUI.md) |
| 📚 **레퍼런스** — 의존성 · 옵션 전체 · 파이프라인 · 출력 구조 · 라이선스 · 한계 · 성능 · 종료 코드 | [docs/REFERENCE.md](docs/REFERENCE.md) |
| 🛠 **개발자** — 빌드 · 테스트 · 포터블 앱 빌드 · 서명 경고 우회 · 소스 구조 | [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) |
| 🏗 **내부 구조 · 설계 결정** | [ARCHITECTURE.md](ARCHITECTURE.md) |

---

## ⚖️ 라이선스 요약

BandPrepare 코드와 대부분의 모델(Demucs / DrumSep / MDX23C / RoFormer)은 MIT 등 상업
이용이 가능한 라이선스입니다. 다만 **드럼 세부 분리 기본 모델 LarsNet의 사전학습
체크포인트는 CC BY-NC 4.0(비상업)** 이라, 그 가중치를 쓴 결과물의 상업적 이용은
제한됩니다. 상업적 용도라면 `--no-drum-split`(1단계 Demucs만) 또는
`--drum-model drumsep` / `mdx23c`(둘 다 MIT)를 쓰세요. 모델별 출처·라이선스 전체는
[docs/REFERENCE.md](docs/REFERENCE.md#모델-출처--라이선스--model-sources--licenses)를 참고하세요.
