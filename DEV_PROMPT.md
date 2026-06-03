# 프로젝트: BandPrepare — 음원 악기 분리 CLI

## 목표
하나의 음원 파일(예: mp3, wav)을 입력으로 받아, 악기별로 분리된 음원 트랙을 생성하는
커맨드라인 프로그램을 개발한다. 특히 드럼 트랙은 한 번 더 분리하여
드럼 키트의 각 구성 악기(킥, 스네어, 하이햇, 크래쉬/심벌, 톰)별 음원까지 만들어낸다.

목적: 밴드 멤버들이 곡을 파트별로 분리해 개별 연습(다른 악기 제거 / 자기 파트만 듣기)에 쓰는 것.

## 처리 파이프라인 (2단계)

### 1단계 — 악기 분리 (stem separation)
- **Demucs** 의 `htdemucs_6s` 모델 사용을 기본으로 한다.
  - 출력 6 stem: `vocals`, `drums`, `bass`, `guitar`, `piano`, `other`
- 모델 가중치는 첫 실행 시 자동 다운로드되도록 한다.

### 2단계 — 드럼 세부 분리 (drum kit separation)
- 1단계에서 나온 `drums` stem을 입력으로 받아 드럼 구성 악기별로 분리한다.
- 권장 모델 (가용성/품질 기준으로 선택, 우선순위 순):
  1. **LarsNet** (`polimi-ispl/larsnet`) — 5 stem: `kick`, `snare`, `toms`, `hihat`, `cymbals`
     - 요구된 분류(킥/스네어/하이햇/크래쉬/톰)와 가장 잘 맞음. (`cymbals` = 크래쉬/라이드)
  2. **DrumSep** (Demucs 기반 드럼 분리 모델) — `kick`, `snare`, `toms`, `cymbals` 등
- 후보 모델을 직접 조사해 설치/실행 가능 여부를 확인하고, 최적의 것을 골라 적용하라.
  설치가 까다로우면 그 이유와 대안을 보고하라.
- 참고: 일반적으로 공개 모델은 "크래쉬"를 단독으로 분리하기보다 `cymbals`(크래쉬+라이드)로
  묶어 출력한다. 단독 크래쉬 분리가 어렵다면 `cymbals`로 출력하고 이 한계를 README에 명시하라.

## CLI 인터페이스

```
bandprepare <input_audio> [options]

옵션:
  -o, --output DIR        출력 디렉터리 (기본: ./output/<입력파일명>/)
  --stems LIST            분리할 악기 선택 (기본: all). 예: vocals,drums,bass
  --no-drum-split         드럼 세부 분리 단계를 건너뜀
  --format {wav,mp3,flac} 출력 포맷 (기본: wav)
  --device {auto,cpu,cuda,mps}  연산 장치 (기본: auto)
  --keep-drums-stem       세부 분리 후에도 원본 drums stem 보존
  -v, --verbose           상세 로그
  --version
```

## 출력 디렉터리 구조 (예시)

```
output/<곡이름>/
├── instruments/
│   ├── vocals.wav
│   ├── bass.wav
│   ├── guitar.wav
│   ├── piano.wav
│   ├── other.wav
│   └── drums.wav            (--keep-drums-stem 시)
└── drums/
    ├── kick.wav
    ├── snare.wav
    ├── hihat.wav
    ├── cymbals.wav          (크래쉬/라이드)
    └── toms.wav
```

## 기술 스택 / 제약
- 언어: **Python 3.10+** (소스 분리 ML 생태계가 Python 기반이라 필수에 가까움).
- 의존성 관리: `pyproject.toml` 또는 `requirements.txt`. 가상환경 사용 전제.
- 핵심 라이브러리: `demucs`, `torch`/`torchaudio`, `ffmpeg`(mp3 등 디코딩/인코딩용), `soundfile`.
- 입력 포맷: ffmpeg가 디코딩 가능한 포맷 전반(mp3, wav, flac, m4a 등) 지원.
- GPU(CUDA), Apple Silicon(MPS), CPU 모두에서 동작. `--device auto`는 가용 가속기를 자동 감지.

## 비기능 요구사항
- **진행 상황 표시**: 단계별 진행률/현재 작업을 콘솔에 표시(특히 CPU에서는 오래 걸림).
- **오류 처리**: 잘못된 입력 파일, ffmpeg 미설치, 모델 다운로드 실패 등에 대해
  명확한 한국어/영어 에러 메시지와 종료 코드를 제공.
- **재실행 안전성**: 이미 생성된 출력이 있으면 덮어쓸지/건너뛸지 처리(필요시 `--overwrite` 추가).
- **성능 메모**: 대략적인 처리 시간/메모리 요구사항을 README에 기록.

## 산출물 (Deliverables)
1. 동작하는 CLI 프로그램 소스 코드 (모듈 구조로 정리: 입력 처리 / 1단계 / 2단계 / 출력).
2. `README.md` — 설치 방법(ffmpeg 포함), 사용 예시, 모델 출처, 알려진 한계.
3. 의존성 정의 파일.
4. 짧은 샘플 음원 1개로 실제 분리가 동작하는지 보여주는 실행 예시 또는 테스트.

## 작업 방식
- 먼저 1단계(Demucs 악기 분리)만으로 end-to-end 동작하는 최소 버전을 완성하고 검증한 뒤,
  2단계(드럼 세부 분리)를 추가하라.
- 외부 모델 선택/설치 과정에서 막히면 임의로 진행하지 말고 발견한 제약과 대안을 보고하라.
- 각 단계가 실제 오디오 파일에서 동작하는지 직접 실행해 확인한 결과를 함께 제시하라.
