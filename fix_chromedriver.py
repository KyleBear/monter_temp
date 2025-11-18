"""
ChromeDriver 문제 해결 스크립트
- 손상된 ChromeDriver 캐시 삭제
- 올바른 아키텍처의 ChromeDriver 재다운로드
"""
import os
import shutil
import platform
import subprocess
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_system_info():
    """시스템 정보 확인"""
    system = platform.system()
    machine = platform.machine()
    architecture = platform.architecture()[0]
    
    print("=" * 60)
    print("시스템 정보")
    print("=" * 60)
    print(f"운영체제: {system}")
    print(f"머신: {machine}")
    print(f"아키텍처: {architecture}")
    print()
    
    return system, machine, architecture

def clear_chromedriver_cache(remove_win32_only=False):
    """ChromeDriver 캐시 삭제
    
    Args:
        remove_win32_only: True이면 win32 버전만 삭제, False이면 전체 캐시 삭제
    """
    print("=" * 60)
    if remove_win32_only:
        print("ChromeDriver win32 버전 삭제")
    else:
        print("ChromeDriver 캐시 삭제")
    print("=" * 60)
    
    system = platform.system()
    
    if remove_win32_only and system == 'Windows':
        # win32 버전만 삭제
        wdm_path = os.path.expanduser(r"~\.wdm\drivers\chromedriver")
        deleted_count = 0
        
        if os.path.exists(wdm_path):
            try:
                # win32가 포함된 경로 찾기
                for root, dirs, files in os.walk(wdm_path):
                    # win32가 경로에 포함된 경우
                    if 'win32' in root:
                        try:
                            print(f"win32 버전 삭제 중: {root}")
                            shutil.rmtree(root)
                            print(f"[OK] 삭제 완료: {root}")
                            deleted_count += 1
                        except Exception as e:
                            print(f"[WARN] 삭제 실패: {root} - {e}")
            except Exception as e:
                print(f"[WARN] win32 버전 검색 실패: {e}")
        
        if deleted_count > 0:
            print(f"\n[SUCCESS] {deleted_count}개 win32 버전 삭제 완료")
        else:
            print("\n[INFO] 삭제할 win32 버전이 없습니다.")
    else:
        # 전체 캐시 삭제
        if system == 'Windows':
            cache_paths = [
                os.path.expanduser(r"~\.wdm"),
                os.path.expanduser(r"~\.cache\selenium"),
            ]
        else:
            cache_paths = [
                os.path.expanduser("~/.wdm"),
                os.path.expanduser("~/.cache/selenium"),
            ]
        
        deleted_count = 0
        for cache_path in cache_paths:
            if os.path.exists(cache_path):
                try:
                    print(f"캐시 삭제 중: {cache_path}")
                    shutil.rmtree(cache_path)
                    print(f"[OK] 삭제 완료: {cache_path}")
                    deleted_count += 1
                except Exception as e:
                    print(f"[WARN] 삭제 실패: {cache_path} - {e}")
            else:
                print(f"[INFO] 캐시 없음: {cache_path}")
        
        if deleted_count > 0:
            print(f"\n[SUCCESS] {deleted_count}개 캐시 디렉토리 삭제 완료")
        else:
            print("\n[INFO] 삭제할 캐시가 없습니다.")
    
    print()

def reinstall_chromedriver(chrome_version=None):
    """ChromeDriver 재설치
    
    Args:
        chrome_version: Chrome 버전 (예: "138.0.7204.179" 또는 "138")
                       None이면 최신 버전 설치
    """
    print("=" * 60)
    print("ChromeDriver 재설치")
    print("=" * 60)
    
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        from webdriver_manager.core.os_manager import OperationSystemManager
        
        # win64를 강제로 선택하는 커스텀 ChromeDriverManager
        class Win64ChromeDriverManager(ChromeDriverManager):
            def get_os_type(self):
                os_type = super().get_os_type()
                # ChromeDriverManager의 get_os_type()이 win32를 반환하므로 win64로 변경
                if "win" in os_type.lower() or os_type == "win32":
                    return "win64"
                return os_type
        
        if chrome_version:
            print(f"Chrome 버전에 맞는 ChromeDriver 다운로드 중... (버전: {chrome_version})")
            print("[INFO] win64 버전을 강제로 다운로드합니다.")
            # 버전 번호만 추출 (예: "138.0.7204.179" -> "138")
            try:
                major_version = chrome_version.split('.')[0]
                print(f"메이저 버전: {major_version}")
            except:
                major_version = chrome_version
        else:
            print("최신 ChromeDriver 다운로드 중...")
            print("[INFO] win64 버전을 강제로 다운로드합니다.")
            major_version = None
        
        # 특정 버전 지정
        if major_version:
            try:
                # Win64ChromeDriverManager 사용 (win64 강제)
                manager = Win64ChromeDriverManager(driver_version=major_version)
                print(f"버전 {major_version}의 ChromeDriver 설치 시도 (win64)...")
                driver_path = manager.install()
            except Exception as e:
                print(f"[WARN] 버전 {major_version} 설치 실패: {e}")
                print("최신 버전으로 시도합니다...")
                manager = Win64ChromeDriverManager()
                driver_path = manager.install()
        else:
            # 캐시 삭제 후 재설치 (win64 강제)
            manager = Win64ChromeDriverManager()
            driver_path = manager.install()
        
        print(f"[OK] ChromeDriver 설치 완료: {driver_path}")
        
        # 파일 확인
        if os.path.exists(driver_path):
            file_size = os.path.getsize(driver_path)
            print(f"[INFO] 파일 크기: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
            
            # 실행 테스트
            print("\n실행 테스트 중...")
            system = platform.system()
            if system == 'Windows':
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
                print(f"[OK] ChromeDriver 실행 성공")
                print(f"[INFO] 버전: {version}")
                return True
            else:
                print(f"[FAIL] ChromeDriver 실행 실패")
                if result.stderr:
                    print(f"[ERROR] {result.stderr}")
                return False
        else:
            print(f"[FAIL] ChromeDriver 파일이 존재하지 않습니다: {driver_path}")
            return False
            
    except ImportError:
        print("[FAIL] webdriver_manager 모듈이 설치되지 않았습니다.")
        print("       설치: pip install webdriver-manager")
        return False
    except Exception as e:
        print(f"[FAIL] ChromeDriver 재설치 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_chrome_version():
    """Chrome 버전 확인"""
    print("=" * 60)
    print("Chrome 버전 확인")
    print("=" * 60)
    
    system = platform.system()
    
    try:
        if system == 'Windows':
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
                        # 버전 번호 추출 (예: "Google Chrome 142.0.7444.163" -> "142")
                        try:
                            version_num = version.split()[-1].split('.')[0]
                            print(f"[INFO] 메이저 버전: {version_num}")
                            return version_num
                        except:
                            pass
                        return version
        else:
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

def main():
    """메인 함수"""
    print("\n" + "=" * 60)
    print("ChromeDriver 문제 해결 도구")
    print("=" * 60)
    print()
    
    # 시스템 정보 확인
    system, machine, architecture = get_system_info()
    
    # Chrome 버전 확인
    chrome_version = check_chrome_version()
    print()
    
    # 명령줄 인자 또는 휴대폰 Chrome 버전 지정
    target_version = None
    remove_win32_only = False
    
    # 명령줄 인자 확인
    if len(sys.argv) > 1:
        if sys.argv[1] == '--remove-win32':
            remove_win32_only = True
            if len(sys.argv) > 2:
                target_version = sys.argv[2]
            else:
                target_version = "138"
        else:
            target_version = sys.argv[1]
        print(f"[INFO] 명령줄 인자로 버전 지정: {target_version}")
    else:
        # 기본값: 휴대폰 Chrome 버전 138
        target_version = "138"
        print("=" * 60)
        print("Chrome 버전 설정")
        print("=" * 60)
        print(f"휴대폰 Chrome 버전 138에 맞는 ChromeDriver를 설치합니다.")
        print(f"다른 버전을 사용하려면: python fix_chromedriver.py <버전>")
        print(f"예: python fix_chromedriver.py 138.0.7204.179")
    print()
    
    # 캐시 삭제 (win32만 삭제 또는 전체 삭제)
    clear_chromedriver_cache(remove_win32_only=remove_win32_only)
    
    # ChromeDriver 재설치
    success = reinstall_chromedriver(target_version)
    
    # 최종 결과
    print("\n" + "=" * 60)
    print("최종 결과")
    print("=" * 60)
    if success:
        print("[SUCCESS] ChromeDriver 재설치 완료")
        print("이제 crawler.py를 다시 실행해보세요.")
    else:
        print("[FAIL] ChromeDriver 재설치 실패")
        print("수동으로 ChromeDriver를 다운로드해야 할 수 있습니다.")
        print("다운로드: https://chromedriver.chromium.org/downloads")
        if chrome_version:
            print(f"Chrome 버전에 맞는 ChromeDriver를 다운로드하세요 (메이저 버전: {chrome_version})")
    
    print("=" * 60)

if __name__ == '__main__':
    main()

