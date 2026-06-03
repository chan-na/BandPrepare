# BandPrepare 🥁🎸

음원 한 곡을 **악기별 트랙**으로 분리하고, **드럼은 다시 킥/스네어/하이햇/심벌/톰**으로
세분화해 주는 커맨드라인 도구입니다. 밴드 멤버가 곡을 파트별로 나눠 개별 연습
(다른 악기 빼기 / 내 파트만 듣기)에 쓰는 것을 목표로 합니다.

A CLI that splits a song into per-instrument stems and further splits the drum
stem into individual kit pieces, so band members can practice their part in
isolation.

---

## 처리 파이프라인 / Pipeline

| 단계 | 모델 | 출력 |
|------|------|------|
| **1. 악기 분리** | [Demucs `htdemucs_6s`](https://github.com/facebookresearch/demucs) | `vocals`, `drums`, `bass`, `guitar`, `piano`, `other` |
| **2. 드럼 세부 분리** | [LarsNet](https://github.com/polimi-ispl/larsnet) | `kick`, `snare`, `hihat`, `cymbals`(크래쉬+라이드), `toms` |

- 1단계 모델 가중치는 첫 실행 시 자동 다운로드됩니다(`~/.cache/torch`).
- 2단계(LarsNet) 체크포인트(약 562 MB)도 첫 실행 시 자동 다운로드되어
  `~/.cache/bandprepare/larsnet` 에 캐시됩니다.

---

## 설치 / Installation

### 1) 사전 준비 (ffmpeg)

mp3·m4a 등 압축 포맷 디코딩에 **ffmpeg**가 필요합니다.

```bash
# macOS
brew install ffmpeg
# Ubuntu/Debian
sudo apt install ffmpeg
```

> wav/flac 입력만 쓴다면 ffmpeg 없이도 동작합니다(torchaudio 직접 디코딩).

### 2) Python 3.10+ 가상환경 + 설치

[`uv`](https://github.com/astral-sh/uv) 사용(권장):

```bash
uv venv --python 3.11 .venv
uv pip install -e .            # 또는: uv pip install -e ".[dev]"
```

또는 표준 `pip`:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
```

설치 후 `bandprepare` 명령과 `python -m bandprepare` 둘 다 사용 가능합니다.

> **플랫폼 메모**: `torch`/`torchaudio`는 `<2.3`으로 고정되어 있습니다. Intel(x86_64)
> macOS용 PyTorch 휠은 2.2.2가 마지막이기 때문입니다. Linux·Apple Silicon에서도
> 이 범위가 정상적으로 설치됩니다.

---

## 사용법 / Usage

```
bandprepare <input_audio> [options]

옵션:
  -o, --output DIR              출력 디렉터리 (기본: ./output/<입력파일명>/)
  --stems LIST                  분리할 악기 선택 (기본: all). 예: vocals,drums,bass
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

### 예시 / Examples

```bash
# 전체 분리 (악기 6종 + 드럼 5종)
bandprepare song.mp3

# 출력 폴더 지정 + flac
bandprepare song.wav -o out/ --format flac

# 보컬·드럼·베이스만, 드럼 세부 분리 포함
bandprepare song.mp3 --stems vocals,drums,bass

# 드럼 세부 분리 없이 6-스템만, CPU 강제
bandprepare song.mp3 --no-drum-split --device cpu
```

---

## 출력 구조 / Output layout

```
output/<곡이름>/
├── instruments/
│   ├── vocals.wav
│   ├── bass.wav
│   ├── guitar.wav
│   ├── piano.wav
│   ├── other.wav
│   └── drums.wav            # --keep-drums-stem 또는 --no-drum-split 시
└── drums/
    ├── kick.wav
    ├── snare.wav
    ├── hihat.wav
    ├── cymbals.wav          # 크래쉬 + 라이드
    └── toms.wav
```

`--stems` 로 일부만 선택하면 해당 파일만 생성됩니다. `drums` 를 선택하지 않으면
드럼 세부 분리도 수행하지 않습니다.

---

## 동작 확인 (샘플 실행) / Verified run

저장소에는 짧은 합성 샘플 생성기가 포함돼 있습니다(실제 음악이 아니라 베이스+드럼+멜로디를
합성한 6초 클립으로, 파이프라인 동작 확인용):

```bash
python tests/make_sample.py -o assets/sample.wav
bandprepare assets/sample.wav -o output/sample
```

실제 Intel macOS(CPU)에서 6초 클립 전체 파이프라인 실행 결과 — 가중치 캐시 후 약 **11초**,
파일 10개 생성:

```
output/sample/
├── instruments/   vocals.wav  bass.wav  guitar.wav  piano.wav  other.wav
└── drums/         kick.wav  snare.wav  hihat.wav  cymbals.wav  toms.wav
```

분리가 실제로 동작함을 보여주는 증거(드럼 5종의 스펙트럼 중심 주파수):

| 트랙 | 스펙트럼 중심 | 해석 |
|------|---------------|------|
| `kick`    |   ~383 Hz | 저역 → 킥 ✔ |
| `toms`    | ~1340 Hz | 중역 → 톰 ✔ |
| `hihat`   | ~10 kHz  | 고역 → 하이햇 ✔ |
| `snare`   | ~10 kHz  | 고역 노이즈 → 스네어 ✔ |
| `cymbals` | (무음)   | 합성 클립에 심벌 없음 → 거의 0 ✔ |

> 합성 클립이라 분리 품질 자체를 평가하긴 어렵지만, 에너지가 올바른 트랙으로 가는 것은
> 확인됩니다. 실제 품질은 실제 음악 파일로 확인하세요.

---

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

### 후보 모델 조사 메모

요구 분류(킥/스네어/하이햇/크래쉬/톰)에 가장 잘 맞는 것은 **LarsNet**(5 stem:
kick/snare/toms/hihat/**cymbals**)이라 이를 채택했습니다. 대안인
[DrumSep](https://github.com/inagoy/drumsep)(Hybrid Demucs 기반)도 검토했으나
기본 4 stem(kick/snare/cymbals/toms)으로 하이햇이 별도 분리되지 않아 후순위로 두었습니다.

---

## 알려진 한계 / Known limitations

- **크래쉬 단독 분리 불가**: 공개 모델은 크래쉬를 단독으로 내보내지 않습니다. 본 도구는
  크래쉬와 라이드를 묶어 `cymbals.wav` 로 출력합니다.
- **분리 누설(bleed)**: 완벽 분리가 아니며, 트랙 간 약간의 누설이 있습니다. 드럼 단계는
  α-Wiener 필터(`--drum-wiener`, 기본 on)로 누설을 줄입니다.
- **CPU 속도**: GPU가 없으면 곡 길이에 비례해 오래 걸립니다(아래 성능 메모 참고).
- **MPS(Apple/Metal)**:
  - Apple Silicon에서는 `auto`가 MPS를 선택합니다. **Intel Mac**(AMD GPU)에서는 MPS가
    "사용 가능"으로 보고되지만 이 모델들에선 CPU보다 느리거나 멈추는 경우가 많아, `auto`는
    Intel Mac에서 의도적으로 CPU를 선택합니다(`--device mps`로 강제 가능).
  - 또한 LarsNet의 일부 복소수 STFT 연산이 MPS에서 미지원일 수 있어, 드럼 단계는 MPS 실행
    실패 시 자동으로 CPU로 폴백합니다.
- **상업적 이용 제한**: 위 라이선스 메모 참고.

---

## 성능 메모 / Performance notes

관측치: 6초 클립 전체 파이프라인이 Intel macOS **CPU**에서 약 11초(1단계 ~7–8초 +
2단계 ~3초, 가중치 캐시 후). 대략적인 환산(`shifts=1` 기본):

| 장치 | 1단계(Demucs) | 2단계(LarsNet) | 메모리 |
|------|---------------|----------------|--------|
| CPU | 곡 길이의 1–2배 정도 | 수~수십 초 | ~2–4 GB RAM |
| CUDA GPU | 수 초~수십 초 | 수 초 | ~2–4 GB VRAM |

- 첫 실행에는 모델 다운로드 시간이 추가됩니다(Demucs 약 300 MB + LarsNet 562 MB).
- 긴 곡은 메모리에 따라 더 오래 걸릴 수 있습니다. CPU에서도 진행 막대가 표시됩니다.
- 더 빠르게: 품질을 조금 양보하고 `--no-drum-wiener`(드럼 단계 가속) 또는
  `--no-drum-split`(2단계 생략)을 쓸 수 있습니다.

---

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

오류 메시지는 한국어/영어로 함께 표시됩니다.

---

## 개발 / Development

```bash
uv pip install -e ".[dev]"
pytest -q                      # 모델 없이 도는 빠른 단위 테스트
```

`pytest` 단위 테스트는 모델 가중치를 받지 않는 빠른 테스트만 포함합니다(인자 파싱,
출력 경로 계획, 샘플 생성 등). 실제 분리는 위 "동작 확인" 절차로 수행합니다.

### 구조

```
src/bandprepare/
├── cli.py                 # 인자 파싱 / 진입점
├── pipeline.py            # 단계 오케스트레이션
├── audio.py               # 입출력 / ffmpeg 점검
├── device.py              # --device 해석
├── separation/
│   ├── stems.py           # 1단계: Demucs
│   └── drums.py           # 2단계: LarsNet 래퍼 + 체크포인트 다운로드
└── vendor/larsnet/        # 벤더링된 LarsNet 모델 코드
```
