"""
Chrome 브라우저 설치 여부 및 ChromeDriver 접근 권한 확인 스크립트
"""
import os
import platform
import subprocess
import logging
from pathlib import Path

try:
    from webdriver_manager.chrome import ChromeDriverManager
    HAS_WEBDRIVER_MANAGER = True
except ImportError:
    HAS_WEBDRIVER_MANAGER = False
    print("[WARN] webdriver_manager 모듈이 설치되지 않았습니다.")
    print("       ChromeDriver 경로는 수동으로 확인합니다.")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_chrome_installation():
    """Chrome 브라우저 설치 여부 확인"""
    print("=" * 60)
    print("Chrome 브라우저 설치 확인")
    print("=" * 60)
    
    system = platform.system()
    chrome_paths = []
    
    if system == 'Windows':
        # Windows에서 Chrome 설치 경로 확인
        possible_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                chrome_paths.append(path)
                print(f"[OK] Chrome 발견: {path}")
        
        # 레지스트리로도 확인 시도
        try:
            result = subprocess.run(
                ['reg', 'query', 'HKEY_CURRENT_USER\\Software\\Google\\Chrome\\BLBeacon', '/v', 'version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                version_line = [line for line in result.stdout.split('\n') if 'version' in line.lower()]
                if version_line:
                    print(f"[OK] Chrome 버전 정보 (레지스트리): {version_line[0].strip()}")
        except Exception as e:
            logger.debug(f"레지스트리 확인 실패: {e}")
    
    elif system == 'Darwin':  # macOS
        possible_paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                chrome_paths.append(path)
                print(f"[OK] Chrome 발견: {path}")
    
    elif system == 'Linux':
        # Linux에서 which 명령으로 확인
        try:
            result = subprocess.run(
                ['which', 'google-chrome'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                chrome_path = result.stdout.strip()
                chrome_paths.append(chrome_path)
                print(f"[OK] Chrome 발견: {chrome_path}")
        except Exception as e:
            logger.debug(f"which 명령 실패: {e}")
        
        # 다른 가능한 경로들
        possible_paths = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium-browser",
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                chrome_paths.append(path)
                print(f"[OK] Chrome 발견: {path}")
    
    if not chrome_paths:
        print("[FAIL] Chrome 브라우저를 찾을 수 없습니다.")
        print("       Chrome을 설치하거나, 설치 경로를 확인하세요.")
        return False
    else:
        print(f"\n[SUCCESS] Chrome 브라우저가 설치되어 있습니다. ({len(chrome_paths)}개 경로 발견)")
        return True


def check_chrome_version():
    """Chrome 버전 확인"""
    print("\n" + "=" * 60)
    print("Chrome 버전 확인")
    print("=" * 60)
    
    system = platform.system()
    
    try:
        if system == 'Windows':
            # Windows에서 Chrome 버전 확인
            chrome_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
            ]
            
            for chrome_path in chrome_paths:
                if os.path.exists(chrome_path):
                    result = subprocess.run(
                        [chrome_path, '--version'],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if result.returncode == 0:
                        version = result.stdout.strip()
                        print(f"[OK] Chrome 버전: {version}")
                        return version
        else:
            # Linux/macOS
            result = subprocess.run(
                ['google-chrome', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                print(f"[OK] Chrome 버전: {version}")
                return version
    except Exception as e:
        print(f"[WARN] Chrome 버전 확인 실패: {e}")
    
    return None


def check_chromedriver():
    """ChromeDriver 설치 및 접근 권한 확인"""
    print("\n" + "=" * 60)
    print("ChromeDriver 확인")
    print("=" * 60)
    
    system = platform.system()
    driver_name = 'chromedriver.exe' if system == 'Windows' else 'chromedriver'
    
    try:
        manager_path = None
        
        if HAS_WEBDRIVER_MANAGER:
            # webdriver-manager로 ChromeDriver 경로 확인
            print("webdriver-manager로 ChromeDriver 다운로드/확인 중...")
            manager_path = ChromeDriverManager().install()
            print(f"[OK] ChromeDriverManager 경로: {manager_path}")
        else:
            # webdriver_manager가 없으면 일반적인 경로에서 찾기
            print("일반적인 경로에서 ChromeDriver 찾는 중...")
            possible_paths = []
            
            if system == 'Windows':
                user_cache = os.path.expanduser(r"~\.wdm\drivers\chromedriver")
                possible_paths = [
                    user_cache,
                    os.path.join(os.getcwd(), 'chromedriver.exe'),
                    os.path.join(os.getcwd(), 'chromedriver'),
                ]
            else:
                possible_paths = [
                    os.path.expanduser("~/.wdm/drivers/chromedriver"),
                    "/usr/local/bin/chromedriver",
                    "/usr/bin/chromedriver",
                    os.path.join(os.getcwd(), 'chromedriver'),
                ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    manager_path = path
                    print(f"[OK] ChromeDriver 경로 발견: {manager_path}")
                    break
            
            if not manager_path:
                print("[WARN] 일반적인 경로에서 ChromeDriver를 찾을 수 없습니다.")
                print("       webdriver_manager를 설치하거나 ChromeDriver를 수동으로 다운로드하세요.")
                return False
        
        # 경로가 디렉토리인지 파일인지 확인
        if os.path.isdir(manager_path):
            search_dir = manager_path
            print(f"[INFO] 디렉토리로 반환됨: {search_dir}")
            
            # 디렉토리 내에서 chromedriver 찾기
            driver_path = None
            for root, dirs, files in os.walk(search_dir):
                for file in files:
                    if file == driver_name:
                        driver_path = os.path.join(root, file)
                        break
                if driver_path:
                    break
            
            if driver_path:
                print(f"[OK] ChromeDriver 파일 발견: {driver_path}")
            else:
                print(f"[WARN] 디렉토리 내에서 {driver_name} 파일을 찾을 수 없습니다.")
                return False
        else:
            driver_path = manager_path
            print(f"[OK] ChromeDriver 파일 경로: {driver_path}")
        
        # 파일 존재 확인
        if not os.path.exists(driver_path):
            print(f"[FAIL] ChromeDriver 파일이 존재하지 않습니다: {driver_path}")
            return False
        
        print(f"[OK] ChromeDriver 파일 존재 확인: {driver_path}")
        
        # 파일 크기 확인
        file_size = os.path.getsize(driver_path)
        
        # 읽기 권한
# 238-241줄 수정
        # 읽기 권한
        if not os.access(driver_path, os.R_OK):
            print(f"[FAIL] ChromeDriver 파일에 읽기 권한이 없습니다: {driver_path}")
            return False
        print(f"[OK] ChromeDriver 파일 읽기 권한 확인")
        
        # 실행 권한 (Windows에서는 항상 True)
        if system != 'Windows':
            if not os.access(driver_path, os.X_OK):
                print(f"[FAIL] ChromeDriver 파일에 실행 권한이 없습니다: {driver_path}")
                return False
            print(f"[OK] ChromeDriver 파일 실행 권한 확인")
        else:
            print(f"[OK] Windows 환경 - 실행 권한 확인 불필요")
        
        # # 실행 권한 (Windows에서는 항상 True)
        # if system == 'Windows':
            
        # else:
        #     if os.access(driver_path, os.X_OK):
        #     else:
        
        # 파일 권한 상세 정보 (Unix 계열)
        if system != 'Windows':
            try:
                stat_info = os.stat(driver_path)
            except Exception as e:
                logger.debug(f"권한 정보 조회 실패: {e}")
        
        # 실제 실행 테스트
        try:
            if system == 'Windows':
                # Windows에서는 --version 옵션으로 테스트
                result = subprocess.run(
                    [driver_path, '--version'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
            else:
                result = subprocess.run(
                    [driver_path, '--version'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
            
            if result.returncode == 0:
                version = result.stdout.strip()
                return True
            else:
                if result.stderr:
                    return False
        except Exception as e:
            return False
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False


def main():
    """메인 함수"""
    print("\n" + "=" * 60)
    print("Chrome 및 ChromeDriver 환경 확인")
    print("=" * 60)
    print(f"운영체제: {platform.system()} {platform.release()}")
    print(f"아키텍처: {platform.machine()}")
    print()
    
    # Chrome 설치 확인
    chrome_installed = check_chrome_installation()
    
    # Chrome 버전 확인
    if chrome_installed:
        check_chrome_version()
    
    # ChromeDriver 확인
    chromedriver_ok = check_chromedriver()
    
    # 최종 결과
    print("\n" + "=" * 60)
    print("최종 결과")
    print("=" * 60)
    print(f"Chrome 브라우저: {'[OK] 설치됨' if chrome_installed else '[FAIL] 설치 안됨'}")
    print(f"ChromeDriver: {'[OK] 정상' if chromedriver_ok else '[FAIL] 문제 있음'}")
    
    if chrome_installed and chromedriver_ok:
        print("\n[SUCCESS] 모든 확인 완료. Chrome과 ChromeDriver가 정상적으로 설정되어 있습니다.")
    else:
        print("\n[WARN] 일부 문제가 발견되었습니다. 위의 메시지를 확인하세요.")


if __name__ == '__main__':
    main()

