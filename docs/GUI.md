# BandPrepare — 그래픽 인터페이스(GUI) 사용 가이드

터미널이 익숙하지 않다면 데스크톱 GUI로도 쓸 수 있습니다. **설치 없이** 받아서 곡을
끌어다 놓고 버튼만 누르면 됩니다. GUI는 [CLI](CLI.md)와 **같은 코어**를 쓰므로
결과물·모델·옵션은 동일합니다.

> A desktop GUI that wraps the same core as the [CLI](CLI.md): same outputs,
> same models, same options — just drag, drop and click. Download the portable
> bundle (no Python/ffmpeg/torch install needed) and double-click `bandprepare`.

---

## 받아서 실행하기 (포터블 앱)

1. [Releases](../../../releases)에서 내 OS용 파일을 받습니다(자세한 파일 이름·표는
   [CLI 가이드 STEP 2](CLI.md#step-2-받아서-준비하기-포터블-앱) 참고).
   `macos-arm64`(애플 실리콘) · `macos-x86_64`(인텔 맥) · `linux-cpu-only` · `windows-cpu-only`
   — **NVIDIA GPU가 있으면** `linux-cuda` / `windows-cuda`(CUDA 가속). `-cuda` 는 용량 때문에
   여러 조각으로 나뉘어 있어 받은 뒤 합쳐야 합니다([CLI STEP 2-1](CLI.md#step-2-받아서-준비하기-포터블-앱)).
2. 압축을 풀면 — **macOS는 `BandPrepare.app`**, **Linux·Windows는 `bandprepare/` 폴더**가 나옵니다.
3. **첫 실행 경고 우회**(한 번만):
   - **macOS**: `BandPrepare.app` 을 **우클릭 → 열기 → 열기**. (또는 터미널에서
     `xattr -dr com.apple.quarantine BandPrepare.app`.)
   - **Windows**: SmartScreen "Windows의 PC 보호" → **추가 정보 → 실행**.
   - 자세히 → [개발 가이드](DEVELOPMENT.md#다운로드한-릴리스-첫-실행-서명-경고-우회)
4. **실행**: macOS는 `BandPrepare.app` 을 **더블클릭**하면 터미널 없이 창이 바로 뜹니다.
   Linux·Windows는 폴더 안 **`bandprepare` 를 더블클릭**하면 창이 뜹니다.

> ⚠️ **이름 주의**: macOS에서 더블클릭하는 건 **`BandPrepare.app`** 입니다(CLI는 앱 안
> `Contents/MacOS/bandprepare-cli`). Linux·Windows 폴더에서는 접미사 **없는** `bandprepare` 가
> **GUI**(더블클릭), `bandprepare-cli` 가 터미널용 CLI예요. (윈도우는 `bandprepare.exe`.)
> 📌 릴리스는 비공개(draft)로 먼저 올라옵니다 — 자산이 안 보이면 공개 전일 수 있습니다.
> 소스에서 직접 빌드해 실행하려면 [개발 가이드](DEVELOPMENT.md#소스에서-설치--install-from-source)를 참고하세요.

---

## 사용법

<!-- TODO: 스크린샷 추가 (docs/images/gui-main.png) -->
<!-- ![BandPrepare GUI](images/gui-main.png) -->

창은 위에서부터 **입출력 파일 → 스템 모델 → 마이너스원 → 드럼 분리 → 기타** 순의
대분류로 정리돼 있습니다:

1. **입출력 파일**: 맨 위 **입력 방식** 라디오로 **파일 / 유튜브 링크** 중 하나를
   고릅니다(고른 쪽 입력칸만 보입니다). 출력 **포맷**(wav/mp3/flac)도 여기서 고릅니다.
   - **파일 / File**: 음원 파일을 **드래그 앤 드롭**(또는 "파일 선택"). 출력 폴더는
     입력 파일 옆 `BandPrepareOutput/<곡이름>` 으로 자동 설정됩니다(직접 바꿔도 됨).
   - **유튜브 링크 / YouTube link**: **유튜브(또는 다른 사이트) 링크**를 붙여넣으면
     음원을 자동으로 받아 분리합니다. 받은 원본은 결과 폴더에 `source.<확장자>` 로
     함께 저장됩니다. 출력 폴더를 비워 두면 **실행 파일 옆 `BandPrepareOutput/<영상
     제목>`** 에 만들어집니다(소스로 실행 시엔 홈 폴더). 진행 막대는 **다운로드 →
     분리** 순으로 한 번에 이어서 움직입니다.
     > ⚠️ 본인이 권리를 가졌거나 허용된 콘텐츠만 받아 개인 연습 용도로 사용하세요.
2. **스템 모델**: 악기 분리에 쓸 **악기 모델**(기본 `htdemucs_ft`)과 저장할
   **스템 체크박스** 선택 — 선택한 스템마다 분리된 음원이 하나씩 생깁니다.
3. **마이너스원**(선택): 제목 체크박스를 켜면 빼낼 스템을 고를 수 있고, 선택한
   스템을 제외하고 믹스한 새 음원이 생깁니다(꺼져 있으면 만들지 않음).
4. **드럼 분리**(선택, 기본 꺼짐): 제목 체크박스를 켜면 **드럼 모델**(기본 `mdx23c`)을
   고를 수 있고 드럼 스템을 킥/스네어 등 조각으로 나눕니다. 켜는 순간
   **드럼 스템 유지**가 자동으로 함께 켜집니다(원하면 해제 가능).
5. **분리 시작** → 진행 막대 + 로그로 진행 확인. 모델이 도는 동안에도 진행 막대가
   조금씩 계속 움직입니다 (분리는 백그라운드 스레드에서 돌아 창이 멈추지 않습니다)
6. 끝나면 **출력 폴더 열기**

> 💡 2스템 모델(`mel_band_roformer`)처럼 드럼이 없는 모델을 고르면 드럼 분리 대분류
> 전체가 자동으로 비활성화됩니다. RoFormer 모델(`bs_roformer`/`mel_band_roformer`)은
> **포터블 앱에 포함**되어 별도 설치 없이 바로 고를 수 있습니다.

---

## 옵션·모델은 CLI와 동일

GUI의 모델 선택, 스템 체크박스, 마이너스원, 포맷·장치 옵션은 모두 CLI 옵션과 1:1로
대응합니다. 각 옵션이 무슨 일을 하는지(연습 목적별 레시피, 모델별 스템·라이선스,
GPU 가속 등)는 [CLI 가이드](CLI.md)를, 옵션 전체 목록은 [레퍼런스의 "옵션 전체"](REFERENCE.md#옵션-전체--all-options)를 참고하세요.

> 🚀 **GPU 가속**: `…-cuda` 번들로 실행하면 **장치 / Device** 드롭다운의 기본값 `auto` 가 NVIDIA
> GPU(CUDA)를 자동으로 선택합니다(명시하려면 `cuda`). 애플 실리콘은 `mps`(Metal). GPU가 없으면
> 자동으로 CPU로 폴백합니다.

---

> 🖥 터미널로 쓰고 싶다면 → [CLI 가이드](CLI.md) · 📚 옵션·모델·라이선스 → [레퍼런스](REFERENCE.md)
