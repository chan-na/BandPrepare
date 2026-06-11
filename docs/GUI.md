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
   `macos-arm64`(애플 실리콘) · `macos-x86_64`(인텔 맥) · `linux-x86_64` · `windows-x86_64`
2. 압축을 풀면 **`bandprepare/` 폴더**가 나옵니다.
3. **첫 실행 경고 우회**(한 번만): macOS는 `xattr -dr com.apple.quarantine <받은폴더>/bandprepare`,
   Windows는 SmartScreen → 추가 정보 → 실행. (자세히 →
   [개발 가이드](DEVELOPMENT.md#다운로드한-릴리스-첫-실행-서명-경고-우회))
4. 폴더 안의 **`bandprepare` 를 더블클릭**하면 창이 뜹니다.

> ⚠️ **이름 주의**: 포터블 번들에서 접미사 **없는** `bandprepare` 가 **GUI**입니다
> (더블클릭하는 것). `bandprepare-cli` 는 터미널용 CLI예요. (윈도우는 `bandprepare.exe`.)
> 📌 릴리스는 비공개(draft)로 먼저 올라옵니다 — 자산이 안 보이면 공개 전일 수 있습니다.
> 소스에서 직접 빌드해 실행하려면 [개발 가이드](DEVELOPMENT.md#소스에서-설치--install-from-source)를 참고하세요.

---

## 사용법

<!-- TODO: 스크린샷 추가 (docs/images/gui-main.png) -->
<!-- ![BandPrepare GUI](images/gui-main.png) -->

창에서:

1. 음원 파일을 **드래그 앤 드롭**(또는 "파일 선택")
2. 악기/드럼 **모델**, 저장할 **스템 체크박스**, **마이너스원**(빼낼 스템), **포맷**·**장치**, 출력 폴더 선택
3. **분리 시작** → 진행 막대 + 로그로 진행 확인 (분리는 백그라운드 스레드에서 돌아 창이 멈추지 않습니다)
4. 끝나면 **출력 폴더 열기**

> 💡 2스템 모델(`mel_band_roformer`)처럼 드럼이 없는 모델을 고르면 드럼 관련 옵션이
> 자동으로 비활성화됩니다. RoFormer 모델(`bs_roformer`/`mel_band_roformer`)은 **포터블
> 앱에 포함**되어 별도 설치 없이 바로 고를 수 있습니다.

---

## 옵션·모델은 CLI와 동일

GUI의 모델 선택, 스템 체크박스, 마이너스원, 포맷·장치 옵션은 모두 CLI 옵션과 1:1로
대응합니다. 각 옵션이 무슨 일을 하는지(연습 목적별 레시피, 모델별 스템·라이선스,
GPU 가속 등)는 [CLI 가이드](CLI.md)를, 옵션 전체 목록은 [레퍼런스의 "옵션 전체"](REFERENCE.md#옵션-전체--all-options)를 참고하세요.

---

> 🖥 터미널로 쓰고 싶다면 → [CLI 가이드](CLI.md) · 📚 옵션·모델·라이선스 → [레퍼런스](REFERENCE.md)
