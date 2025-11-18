"""
휴대폰에서 Chrome 앱을 껐다 켜는 테스트 스크립트
ADB를 사용하여 Android 기기의 Chrome 앱을 제어합니다.

사용 전 설정:
1. Android 휴대폰에서 개발자 옵션 활성화 및 USB 디버깅 활성화
2. 휴대폰이 USB로 PC에 연결되어 있어야 함
3. ADB가 설치되어 있고 PATH에 추가되어 있어야 함
"""
import time
import logging
import subprocess
import os
import urllib.request
import zipfile
from pathlib import Path
from config import Config

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 전역 변수: ADB 경로
ADB_PATH = None

# ADB 다운로드 URL (최신 안정 버전)
ADB_DOWNLOAD_URLS = {
    'windows': 'https://dl.google.com/android/repository/platform-tools-latest-windows.zip',
    'linux': 'https://dl.google.com/android/repository/platform-tools-latest-linux.zip',
    'darwin': 'https://dl.google.com/android/repository/platform-tools-latest-darwin.zip'
}


def download_adb():
    """ADB 바이너리를 자동으로 다운로드"""
    global ADB_PATH
    
    try:
        # 프로젝트 디렉토리에 adb 폴더 생성
        project_dir = Path(__file__).parent
        adb_dir = project_dir / 'adb'
        adb_dir.mkdir(exist_ok=True)
        
        # OS에 맞는 다운로드 URL 선택
        system = os.name
        if system == 'nt':
            download_url = ADB_DOWNLOAD_URLS['windows']
            adb_exe = adb_dir / 'platform-tools' / 'adb.exe'
        elif system == 'posix':
            import platform
            if platform.system() == 'Darwin':
                download_url = ADB_DOWNLOAD_URLS['darwin']
            else:
                download_url = ADB_DOWNLOAD_URLS['linux']
            adb_exe = adb_dir / 'platform-tools' / 'adb'
        else:
            logger.error("지원하지 않는 운영체제입니다.")
            return None
        
        # 이미 다운로드되어 있으면 사용
        if adb_exe.exists():
            ADB_PATH = str(adb_exe)
            logger.info(f"✓ 기존 ADB를 찾았습니다: {ADB_PATH}")
            return ADB_PATH
        
        # ZIP 파일 다운로드
        zip_path = adb_dir / 'platform-tools.zip'
        logger.info("ADB를 다운로드하는 중...")
        logger.info(f"다운로드 URL: {download_url}")
        
        urllib.request.urlretrieve(download_url, zip_path)
        logger.info("✓ 다운로드 완료")
        
        # ZIP 파일 압축 해제
        logger.info("압축 해제 중...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(adb_dir)
        
        # ZIP 파일 삭제
        zip_path.unlink()
        
        # ADB 실행 파일 확인
        if adb_exe.exists():
            # 실행 권한 부여 (Linux/Mac)
            if system != 'nt':
                os.chmod(adb_exe, 0o755)
            
            ADB_PATH = str(adb_exe)
            logger.info(f"✓ ADB 다운로드 및 설치 완료: {ADB_PATH}")
            return ADB_PATH
        else:
            logger.error("ADB 실행 파일을 찾을 수 없습니다.")
            return None
            
    except Exception as e:
        logger.error(f"ADB 다운로드 중 오류: {e}")
        logger.error("수동으로 ADB를 설치하거나 PATH에 추가하세요.")
        return None


def find_adb_path():
    """ADB 경로를 자동으로 찾기"""
    global ADB_PATH
    
    # 이미 찾았으면 반환
    if ADB_PATH:
        return ADB_PATH
    
    # 0. 프로젝트 디렉토리 내 adb 폴더 확인 (가장 우선)
    project_dir = Path(__file__).parent
    if os.name == 'nt':
        project_adb = project_dir / 'adb' / 'platform-tools' / 'adb.exe'
    else:
        project_adb = project_dir / 'adb' / 'platform-tools' / 'adb'
    
    if project_adb.exists():
        ADB_PATH = str(project_adb)
        logger.info(f"✓ 프로젝트 디렉토리에서 ADB를 찾았습니다: {ADB_PATH}")
        return ADB_PATH
    
    # 1. PATH에서 찾기
    try:
        result = subprocess.run(['adb', 'version'], capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            ADB_PATH = 'adb'
            logger.info("✓ PATH에서 ADB를 찾았습니다.")
            return ADB_PATH
    except:
        pass
    
    # 2. Windows 일반 경로에서 찾기
    if os.name == 'nt':  # Windows
        possible_paths = [
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Android', 'Sdk', 'platform-tools', 'adb.exe'),
            os.path.join(os.environ.get('USERPROFILE', ''), 'AppData', 'Local', 'Android', 'Sdk', 'platform-tools', 'adb.exe'),
            os.path.join(os.environ.get('PROGRAMFILES', ''), 'Android', 'android-sdk', 'platform-tools', 'adb.exe'),
            os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'Android', 'android-sdk', 'platform-tools', 'adb.exe'),
            'C:\\Android\\platform-tools\\adb.exe',
            'C:\\adb\\adb.exe',
        ]
        
        for path in possible_paths:
            if path and os.path.exists(path):
                ADB_PATH = path
                logger.info(f"✓ ADB를 찾았습니다: {path}")
                return ADB_PATH
    
    # 3. Linux/Mac 경로
    else:
        possible_paths = [
            os.path.expanduser('~/Android/Sdk/platform-tools/adb'),
            os.path.expanduser('~/Library/Android/sdk/platform-tools/adb'),
            '/usr/local/bin/adb',
            '/usr/bin/adb',
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                ADB_PATH = path
                logger.info(f"✓ ADB를 찾았습니다: {path}")
                return ADB_PATH
    
    # 4. 자동 다운로드 시도
    logger.info("ADB를 찾을 수 없습니다. 자동 다운로드를 시도합니다...")
    downloaded_path = download_adb()
    if downloaded_path:
        return downloaded_path
    
    logger.error("⚠ ADB를 찾을 수 없습니다.")
    logger.error("다음 중 하나를 시도하세요:")
    logger.error("1. Android SDK Platform Tools 설치")
    logger.error("2. ADB를 PATH에 추가")
    logger.error("3. ADB를 C:\\adb\\ 또는 C:\\Android\\platform-tools\\ 에 설치")
    return None


def run_adb_command(*args):
    """ADB 명령 실행 헬퍼 함수"""
    adb_path = find_adb_path()
    if not adb_path:
        raise FileNotFoundError("ADB를 찾을 수 없습니다.")
    
    cmd = [adb_path] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=10)


def check_adb_connection():
    """ADB 연결 확인"""
    try:
        result = run_adb_command('devices')
        devices = result.stdout.strip().split('\n')[1:]  # 첫 번째 줄(헤더) 제외
        
        connected_devices = [d for d in devices if d.strip() and 'device' in d]
        
        if not connected_devices:
            logger.warning("⚠ USB로 연결된 Android 기기를 찾을 수 없습니다.")
            logger.warning("다음을 확인하세요:")
            logger.warning("1. 휴대폰이 USB로 연결되어 있는지")
            logger.warning("2. USB 디버깅이 활성화되어 있는지")
            logger.warning("3. '이 컴퓨터에서 항상 허용' 체크박스를 선택했는지")
            return False
        
        logger.info(f"✓ {len(connected_devices)}개의 Android 기기가 연결되어 있습니다.")
        return True
        
    except FileNotFoundError:
        return False
    except Exception as e:
        logger.error(f"ADB 연결 확인 중 오류: {e}")
        return False


def close_chrome():
    """휴대폰에서 Chrome 앱 종료"""
    try:
        logger.info("Chrome 앱 종료 중...")
        
        # Chrome 앱 강제 종료
        result = run_adb_command('shell', 'am', 'force-stop', 'com.android.chrome')
        
        if result.returncode == 0:
            logger.info("✓ Chrome 앱 종료 완료")
            time.sleep(2)  # 종료 후 잠시 대기
            return True
        else:
            logger.error(f"Chrome 종료 실패: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Chrome 종료 중 오류: {e}")
        return False


def open_chrome(url=None):
    """휴대폰에서 Chrome 앱 시작"""
    try:
        if url:
            logger.info(f"Chrome 앱을 {url}로 시작 중...")
            # 특정 URL로 Chrome 시작
            result = run_adb_command('shell', 'am', 'start', '-a', 'android.intent.action.VIEW', 
                                     '-d', url, 'com.android.chrome')
        else:
            logger.info("Chrome 앱 시작 중...")
            # Chrome 메인 화면으로 시작
            result = run_adb_command('shell', 'am', 'start', '-n', 
                                     'com.android.chrome/com.google.android.apps.chrome.Main')
        
        if result.returncode == 0:
            logger.info("✓ Chrome 앱 시작 완료")
            time.sleep(3)  # 시작 후 잠시 대기
            return True
        else:
            logger.error(f"Chrome 시작 실패: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Chrome 시작 중 오류: {e}")
        return False


def restart_chrome(url=None):
    """Chrome 앱을 종료하고 다시 시작"""
    logger.info("=" * 50)
    logger.info("Chrome 앱 재시작 시작")
    logger.info("=" * 50)
    
    # Chrome 종료
    if not close_chrome():
        logger.warning("Chrome 종료 실패했지만 계속 진행합니다...")
    
    # 잠시 대기
    time.sleep(2)
    
    # Chrome 시작
    if not open_chrome(url):
        logger.error("Chrome 시작 실패")
        return False
    
    logger.info("=" * 50)
    logger.info("Chrome 앱 재시작 완료")
    logger.info("=" * 50)
    return True


def test_chrome_restart_cycle(count=3, url=None):
    """Chrome을 여러 번 껐다 켜는 테스트"""
    config = Config()
    
    logger.info("=" * 50)
    logger.info("휴대폰 Chrome 재시작 테스트 시작")
    logger.info(f"재시작 횟수: {count}")
    if url:
        logger.info(f"시작 URL: {url}")
    logger.info("=" * 50)
    
    # ADB 연결 확인
    if not check_adb_connection():
        logger.error("ADB 연결 실패. 테스트를 중단합니다.")
        return False
    
    # 여러 번 재시작
    for i in range(count):
        logger.info(f"\n[재시작 {i + 1}/{count}]")
        success = restart_chrome(url)
        
        if success:
            logger.info(f"✓ 재시작 {i + 1} 성공")
        else:
            logger.warning(f"⚠ 재시작 {i + 1} 실패")
        
        # 마지막이 아니면 대기
        if i < count - 1:
            wait_time = config.ACTION_DELAY if hasattr(config, 'ACTION_DELAY') else 5
            logger.info(f"다음 재시작까지 {wait_time}초 대기...")
            time.sleep(wait_time)
    
    logger.info("=" * 50)
    logger.info("모든 재시작 테스트 완료")
    logger.info("=" * 50)


def main():
    """메인 함수"""
    config = Config()
    
    # 네이버 모바일 URL 사용 (선택사항)
    start_url = config.NAVER_MOBILE_URL if hasattr(config, 'NAVER_MOBILE_URL') else None
    
    # Chrome 재시작 테스트 실행
    test_chrome_restart_cycle(count=3, url=start_url)


if __name__ == '__main__':
    main()

