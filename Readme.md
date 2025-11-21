새검색어 입력후 sSearch 시 3초정도 필요 

## 원격 디바이스 (휴대폰) Chrome Selenium 설정

### 연결 방식
- **Chrome DevTools Protocol (CDP)** 사용
- `debuggerAddress` experimental option을 통해 이미 실행 중인 휴대폰 Chrome에 연결
- 연결 주소: `127.0.0.1:{REMOTE_DEBUGGING_PORT}`

### 포트 설정
- **기본 포트**: `9222` (config.py의 `REMOTE_DEBUGGING_PORT`)
- **멀티스레드 사용 시**: `9222`, `9223` (test.py의 `THREAD_PORTS`)
- **ADB 포트 포워딩**: 
  adb forward tcp:{port} localabstract:chrome_devtools_remote
    예: `adb forward tcp:9222 localabstract:chrome_devtools_remote`

### 원격 디바이스에서 사용하는 Chrome 옵션
원격 디바이스(`debuggerAddress` 사용)에서는 이미 실행 중인 Chrome에 연결하므로, 제한된 옵션만 적용됩니다.

#### 적용되는 옵션:
- `--disable-blink-features=AutomationControlled` - 봇 감지 우회
- `--disable-dev-shm-usage` - 공유 메모리 사용 비활성화
- `--disable-application-cache` - 애플리케이션 캐시 비활성화
- `--disable-cache` - 캐시 비활성화
- `--disable-web-security` - 웹 보안 비활성화
- `--disable-features=IsolateOrigins,site-per-process` - 사이트 격리 비활성화
- `--disable-site-isolation-trials` - 사이트 격리 시험 기능 비활성화
- `--lang=ko-KR` - 언어 설정

#### 사용하지 않는 옵션 (파싱 오류 방지):
원격 디바이스에서는 다음 옵션들이 파싱 오류를 일으키므로 제외됩니다:
- `excludeSwitches` (experimental option)
- `useAutomationExtension` (experimental option)
- `prefs` (experimental option)
- `--user-agent` (이미 실행 중인 Chrome에는 적용 불가)
- `--no-sandbox`, `--disable-gpu` 등 (이미 실행 중인 Chrome에는 적용 불가)

### 주의사항
1. 휴대폰에서 Chrome이 실행 중이어야 합니다(설치)
2. USB 디버깅이 활성화되어 있어야 합니다
3. ADB 포트 포워딩이 설정되어 있어야 합니다
4. 각 스레드는 고유한 포트를 사용해야 합니다 (충돌 방지) -- 

-- 크롬 드라이버 버전 
-- 포트 포워딩 도 맞아야됨.

(Android amd 주의사항)
🚫 Chrome DevTools 9222 포트 하나로는 여러 스레드가 동시에 여러 탭을 안정적으로 크롤링할 수 없다.
# 현재 코드는 스레드별 포트 분리로 안전하게 설계됨
# 같은 포트를 여러 스레드가 공유하면 충돌 가능성이 있으므로 현재 구조 유지 권장

page target이 없다 = Chrome이 실제 탭을 열지 않았다 

Chrome 인스턴스 자체를 여러 개 띄우기 (현재)
9222, 9223, 9224… 포트별로 Chrome 실행
Chrome 1 → 9222 → 여러 탭 크롤링
Chrome 2 → 9223 → 여러 탭 크롤링
Chrome 3 → 9224 → 여러 탭 크롤링

락 Driver_생성시 충돌방지
+ 스텔스 모드로 사람처럼 크롤링 
-- 드라이버 적용시 - 일반드라이버 or 셀레니움 드라이버 + 스텔스 스크립트
webdriver.Chrome() 성공 직후 스텔스 스크립트 주입

Android Chrome에서는 여러 탭을 열어도, 백그라운드에서 DevTools로 각각을 제어하는 병렬 크롤링은 불가능하다.
사유-  모든 탭이 단일 WebView 기반 "chrome_devtools_remote" 세션 하나를 공유함. (단일 세션 기반) 

예외적으로 
➜ Android에서 "완전한 Chrome 인스턴스 여러 개" 만들려면?
Android에서 "완전한 Chrome 인스턴스 여러 개" 만들려면?

com.android.chrome (Stable)
com.chrome.beta
com.chrome.dev
com.chrome.canary

앱 복제본 패키지(com.clone.chrome001 등)
이런 식으로 서로 다른 패키지가 필요함.

그래야 ADB로 각 Chrome 프로세스를 독립 제어할 수 있음.
com.android.chrome (Stable)

✔ 앞으로의 구조 -휴대폰
멀티프로세스 → 각 프로세스=Chrome 1개 → DevTools 포트도 각각
Process 1 → Chrome:9221
Process 2 → Chrome:9222
Process 3 → Chrome:9223
Process 4 → Chrome:9224


웹 
"""
SSH 터널(SOCKS Proxy)을 통한 로컬 크롤러
- 내 PC에서 Python 코드 실행
- SSH 터널로 상대방 서버(화이트리스트 IP)에 연결
- 모든 크롤링 트래픽이 상대방 서버 IP로 전송됨
"""

화이트리스트

https://searchadvisor.naver.com/guide/seo-basic-redirect?utm_source=chatgpt.com