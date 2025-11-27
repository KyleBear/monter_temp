@echo off
REM Chrome 138 바이너리 다운로드 스크립트 (CMD)
REM npx를 사용하여 Chrome 138을 다운로드합니다

echo ========================================
echo Chrome 138 바이너리 다운로드 시작
echo ========================================

REM Node.js 설치 확인
where node >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [오류] Node.js가 설치되어 있지 않습니다!
    echo Node.js를 먼저 설치해주세요: https://nodejs.org/
    pause
    exit /b 1
)

echo [확인] Node.js가 설치되어 있습니다.

REM chrome_138_directory 폴더 확인
if not exist "chrome_138_directory" (
    echo [생성] chrome_138_directory 폴더 생성 중...
    mkdir chrome_138_directory
)

REM Chrome 138 다운로드
echo.
echo [다운로드] Chrome 138 다운로드 중...
echo 이 작업은 몇 분이 걸릴 수 있습니다...
echo.

npx --yes @puppeteer/browsers install chrome@138.0.0.0 --path=./chrome_138_directory

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [완료] Chrome 138 다운로드 완료!
    echo.
    echo [참고] 다운로드된 chrome.exe는 다음 경로 중 하나에 있습니다:
    echo    - chrome_138_directory\chrome-win64\chrome.exe
    echo    - chrome_138_directory\chrome-win64\chrome-win64\chrome.exe
    echo.
    echo 코드에서 자동으로 찾습니다.
    echo.
    echo ========================================
    echo 다운로드 완료!
    echo ========================================
) else (
    echo.
    echo [오류] 다운로드 실패!
    pause
    exit /b 1
)

pause


