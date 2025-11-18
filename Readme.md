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