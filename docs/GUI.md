# BandPrepare — 그래픽 인터페이스(GUI) 사용 가이드

터미널이 익숙하지 않다면 데스크톱 GUI로도 쓸 수 있습니다. 곡을 끌어다 놓고 버튼만
누르면 됩니다. GUI는 [CLI](CLI.md)와 **같은 코어**를 쓰므로 결과물·모델·옵션은 동일합니다.

> A desktop GUI that wraps the same core as the [CLI](CLI.md): same outputs,
> same models, same options — just drag, drop and click.

---

## 설치 & 실행

```bash
# GUI 의존성(PySide6) 설치 — 최초 1회
uv pip install -e ".[gui]"     # 또는: pip install -e ".[gui]"

# 실행
bandprepare-gui
```

> 더블클릭으로 실행하는 **포터블 앱**(ffmpeg/Python/torch 사전 설치 불필요)은
> [Releases](../../../releases)에서 받을 수 있습니다. 직접 빌드하려면
> [개발 가이드의 "포터블 앱 빌드"](DEVELOPMENT.md#포터블-앱-빌드-pyinstaller)를 참고하세요.

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
> 자동으로 비활성화됩니다. RoFormer 모델은 `.[roformer]` extra가 설치돼 있어야 합니다.

---

## 옵션·모델은 CLI와 동일

GUI의 모델 선택, 스템 체크박스, 마이너스원, 포맷·장치 옵션은 모두 CLI 옵션과 1:1로
대응합니다. 각 옵션이 무슨 일을 하는지(연습 목적별 레시피, 모델별 스템·라이선스,
GPU 가속 등)는 [CLI 가이드](CLI.md)를, 옵션 전체 목록은 [레퍼런스의 "옵션 전체"](REFERENCE.md#옵션-전체--all-options)를 참고하세요.

---

> 🖥 터미널로 쓰고 싶다면 → [CLI 가이드](CLI.md) · 📚 옵션·모델·라이선스 → [레퍼런스](REFERENCE.md)
