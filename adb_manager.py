"""
ADB Manager - ADB 자동 다운로드 및 관리 모듈

ADB(Android Debug Bridge)를 자동으로 찾거나 다운로드하여 관리합니다.
"""
import os
import sys
import logging
import subprocess
import urllib.request
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)


class ADBManager:
    """ADB 경로 관리 및 자동 다운로드"""
    
    # ADB 다운로드 URL
    DOWNLOAD_URLS = {
        'windows': 'https://dl.google.com/android/repository/platform-tools-latest-windows.zip',
        'linux': 'https://dl.google.com/android/repository/platform-tools-latest-linux.zip',
        'darwin': 'https://dl.google.com/android/repository/platform-tools-latest-darwin.zip'
    }
    
    def __init__(self, project_dir=None):
        """
        Args:
            project_dir: ADB를 저장할 프로젝트 디렉토리 (기본값: 현재 스크립트 위치)
        """
        self.adb_path = None
        self.project_dir = Path(project_dir) if project_dir else Path(__file__).parent
        self.adb_dir = self.project_dir / 'adb'
        self.os_type = self._get_os_type()
        
    def _get_os_type(self):
        """운영체제 타입 확인"""
        if sys.platform.startswith('win'):
            return 'windows'
        elif sys.platform.startswith('darwin'):
            return 'darwin'
        elif sys.platform.startswith('linux'):
            return 'linux'
        return None
    
    def _get_adb_executable_path(self):
        """OS별 ADB 실행 파일 경로"""
        if self.os_type == 'windows':
            return self.adb_dir / 'platform-tools' / 'adb.exe'
        else:
            return self.adb_dir / 'platform-tools' / 'adb'
    
    def _test_adb(self, adb_path):
        """ADB 실행 가능 여부 테스트"""
        try:
            result = subprocess.run(
                [str(adb_path), 'version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def _find_in_project(self):
        """프로젝트 디렉토리에서 ADB 찾기"""
        adb_exe = self._get_adb_executable_path()
        
        if adb_exe.exists() and self._test_adb(adb_exe):
            logger.info(f"✓ 프로젝트 디렉토리에서 ADB 발견: {adb_exe}")
            return str(adb_exe)
        return None
    
    def _find_in_path(self):
        """시스템 PATH에서 ADB 찾기"""
        try:
            result = subprocess.run(
                ['adb', 'version'],
                capture_output=True,
                text=True,
                timeout=3
            )
            if result.returncode == 0:
                logger.info("✓ 시스템 PATH에서 ADB 발견")
                return 'adb'
        except:
            pass
        return None
    
    def download(self, force=False):
        """
        ADB를 자동으로 다운로드
        
        Args:
            force: True면 기존 파일이 있어도 재다운로드
            
        Returns:
            str: ADB 실행 파일 경로 또는 None
        """
        try:
            # OS 확인
            if not self.os_type:
                logger.error("지원하지 않는 운영체제입니다.")
                return None
            
            # 디렉토리 생성
            self.adb_dir.mkdir(exist_ok=True)
            adb_exe = self._get_adb_executable_path()
            
            # 기존 파일 확인 (force가 아닌 경우)
            if not force and adb_exe.exists() and self._test_adb(adb_exe):
                logger.info(f"✓ 기존 ADB를 사용합니다: {adb_exe}")
                return str(adb_exe)
            
            # 다운로드 URL
            download_url = self.DOWNLOAD_URLS[self.os_type]
            zip_path = self.adb_dir / 'platform-tools.zip'
            
            logger.info("=" * 60)
            logger.info("ADB Platform Tools 다운로드 시작")
            logger.info(f"OS: {self.os_type}")
            logger.info(f"URL: {download_url}")
            logger.info("=" * 60)
            
            # 기존 파일 삭제
            if zip_path.exists():
                zip_path.unlink()
            
            # 진행률 표시 콜백
            def show_progress(block_num, block_size, total_size):
                downloaded = block_num * block_size
                percent = min(100, downloaded * 100 / total_size)
                bar_length = 40
                filled = int(bar_length * downloaded / total_size)
                bar = '█' * filled + '-' * (bar_length - filled)
                print(f'\r다운로드: [{bar}] {percent:.1f}% ({downloaded/1024/1024:.1f}MB / {total_size/1024/1024:.1f}MB)', 
                      end='', flush=True)
            
            # ZIP 파일 다운로드
            urllib.request.urlretrieve(download_url, zip_path, show_progress)
            print()  # 줄바꿈
            logger.info("✓ 다운로드 완료")
            
            # 기존 platform-tools 폴더 삭제
            platform_tools_dir = self.adb_dir / 'platform-tools'
            if platform_tools_dir.exists():
                import shutil
                logger.info("기존 platform-tools 폴더 삭제 중...")
                shutil.rmtree(platform_tools_dir)
            
            # ZIP 파일 압축 해제
            logger.info("압축 해제 중...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                total_files = len(zip_ref.namelist())
                for i, file in enumerate(zip_ref.namelist()):
                    zip_ref.extract(file, self.adb_dir)
                    if (i + 1) % 10 == 0 or i == total_files - 1:
                        print(f'\r압축 해제: {i+1}/{total_files} 파일', end='', flush=True)
            print()  # 줄바꿈
            logger.info("✓ 압축 해제 완료")
            
            # ZIP 파일 삭제
            zip_path.unlink()
            logger.info("✓ 임시 파일 삭제 완료")
            
            # ADB 실행 파일 확인
            if not adb_exe.exists():
                logger.error(f"ADB 실행 파일을 찾을 수 없습니다: {adb_exe}")
                return None
            
            # 실행 권한 부여 (Linux/Mac)
            if self.os_type != 'windows':
                os.chmod(adb_exe, 0o755)
                # 다른 실행 파일들도 권한 부여
                for exe_file in platform_tools_dir.glob('*'):
                    if exe_file.is_file() and not exe_file.suffix:
                        try:
                            os.chmod(exe_file, 0o755)
                        except:
                            pass
                logger.info("✓ 실행 권한 설정 완료")
            
            # ADB 버전 확인
            if self._test_adb(adb_exe):
                try:
                    result = subprocess.run(
                        [str(adb_exe), 'version'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    version_line = result.stdout.split('\n')[0]
                    logger.info(f"✓ {version_line}")
                except:
                    pass
            
            logger.info("=" * 60)
            logger.info(f"✓ ADB 설치 완료: {adb_exe}")
            logger.info("=" * 60)
            return str(adb_exe)
            
        except urllib.error.URLError as e:
            logger.error(f"다운로드 실패 (네트워크 오류): {e}")
            logger.error("인터넷 연결을 확인하세요.")
            return None
        except Exception as e:
            logger.error(f"ADB 다운로드 중 오류: {e}")
            return None
    
    def find_or_download(self):
        """
        ADB를 찾거나 자동으로 다운로드
        
        Returns:
            str: ADB 실행 파일 경로 또는 None
        """
        if self.adb_path:
            return self.adb_path
        
        logger.info("ADB를 찾는 중...")
        
        # 1. 프로젝트 디렉토리에서 찾기
        adb_path = self._find_in_project()
        if adb_path:
            self.adb_path = adb_path
            return adb_path
        
        # 2. 시스템 PATH에서 찾기
        adb_path = self._find_in_path()
        if adb_path:
            self.adb_path = adb_path
            return adb_path
        
        # 3. 자동 다운로드
        logger.info("시스템 경로에서 ADB를 찾을 수 없습니다.")
        logger.info("ADB를 자동으로 다운로드합니다...")
        
        adb_path = self.download()
        if adb_path:
            self.adb_path = adb_path
            return adb_path
        
        # 실패
        logger.error("=" * 60)
        logger.error("⚠ ADB를 찾거나 다운로드할 수 없습니다.")
        logger.error("다음을 시도하세요:")
        logger.error("1. 인터넷 연결 확인")
        logger.error("2. 수동으로 Android SDK Platform Tools 설치")
        logger.error("   https://developer.android.com/studio/releases/platform-tools")
        logger.error("=" * 60)
        return None
    
    def get_path(self):
        """현재 ADB 경로 반환 (없으면 찾기 시도)"""
        if not self.adb_path:
            return self.find_or_download()
        return self.adb_path
    
    def run_command(self, *args, timeout=10):
        """
        ADB 명령 실행
        
        Args:
            *args: ADB 명령 인자들
            timeout: 명령 타임아웃 (초)
            
        Returns:
            subprocess.CompletedProcess: 실행 결과
            
        Raises:
            FileNotFoundError: ADB를 찾을 수 없을 때
        """
        adb_path = self.get_path()
        if not adb_path:
            raise FileNotFoundError("ADB를 사용할 수 없습니다.")
        
        cmd = [adb_path] + list(args)
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    
    def check_connection(self):
        """
        ADB 연결 확인
        
        Returns:
            bool: 연결된 기기가 있으면 True
        """
        try:
            result = self.run_command('devices')
            
            # 출력 전체를 로그로 표시 (디버깅용) - INFO 레벨로 변경
            logger.info("=" * 60)
            logger.info("ADB devices 명령 실행 결과:")
            logger.info(f"Return code: {result.returncode}")
            logger.info(f"출력 (stdout):\n{result.stdout}")
            if result.stderr:
                logger.info(f"에러 (stderr):\n{result.stderr}")
            logger.info("=" * 60)
            
            # 헤더 제외하고 디바이스 목록 파싱
            lines = result.stdout.strip().split('\n')
            logger.info(f"파싱된 줄 수: {len(lines)}")
            
            if len(lines) < 2:
                logger.warning("=" * 60)
                logger.warning("⚠ USB로 연결된 Android 기기를 찾을 수 없습니다.")
                logger.warning("")
                logger.warning("다음을 확인하세요:")
                logger.warning("1. 휴대폰이 USB로 PC에 연결되어 있는지")
                logger.warning("2. 휴대폰에서 USB 디버깅이 활성화되어 있는지")
                logger.warning("   (설정 > 개발자 옵션 > USB 디버깅)")
                logger.warning("3. 연결 시 나타나는 '이 컴퓨터를 항상 허용' 선택")
                logger.warning("4. USB 케이블이 데이터 전송을 지원하는지")
                logger.warning("")
                logger.warning(f"실제 ADB 출력:\n{result.stdout}")
                logger.warning("=" * 60)
                return False
            
            devices = lines[1:]  # 첫 번째 줄(헤더) 제외
            logger.info(f"디바이스 줄 수: {len(devices)}")
            
            # 디바이스 상태 파싱
            connected_devices = []
            unauthorized_devices = []
            offline_devices = []
            
            for i, line in enumerate(devices):
                line = line.strip()
                logger.info(f"디바이스 줄 {i+1}: '{line}'")
                if not line:
                    continue
                
                # 탭이나 공백으로 구분 (시리얼번호\t상태 형식)
                parts = line.split()
                logger.info(f"  파싱된 부분: {parts}")
                if len(parts) >= 2:
                    serial = parts[0]
                    status = parts[1]
                    logger.info(f"  시리얼: {serial}, 상태: {status}")
                    
                    if status == 'device':
                        connected_devices.append(line)
                    elif status == 'unauthorized':
                        unauthorized_devices.append(serial)
                    elif status == 'offline':
                        offline_devices.append(serial)
                else:
                    logger.warning(f"  ⚠ 예상치 못한 형식: '{line}' (부분 수: {len(parts)})")
            
            # 상태별 메시지 출력
            if unauthorized_devices:
                logger.warning("=" * 60)
                logger.warning("⚠ 인증되지 않은 기기가 있습니다:")
                for serial in unauthorized_devices:
                    logger.warning(f"  - {serial}")
                logger.warning("")
                logger.warning("휴대폰 화면에서 '이 컴퓨터를 항상 허용'을 선택하고 확인을 누르세요.")
                logger.warning("=" * 60)
            
            if offline_devices:
                logger.warning("⚠ 오프라인 상태인 기기가 있습니다:")
                for serial in offline_devices:
                    logger.warning(f"  - {serial}")
                logger.warning("USB 케이블을 다시 연결하거나 휴대폰을 재부팅해보세요.")
            
            if not connected_devices:
                logger.warning("=" * 60)
                logger.warning("⚠ USB로 연결된 Android 기기를 찾을 수 없습니다.")
                logger.warning("")
                logger.warning("다음을 확인하세요:")
                logger.warning("1. 휴대폰이 USB로 PC에 연결되어 있는지")
                logger.warning("2. 휴대폰에서 USB 디버깅이 활성화되어 있는지")
                logger.warning("   (설정 > 개발자 옵션 > USB 디버깅)")
                logger.warning("3. 연결 시 나타나는 '이 컴퓨터를 항상 허용' 선택")
                logger.warning("4. USB 케이블이 데이터 전송을 지원하는지")
                logger.warning("")
                logger.warning(f"실제 ADB 출력:\n{result.stdout}")
                logger.warning(f"파싱된 디바이스 줄: {devices}")
                logger.warning("=" * 60)
                return False
            
            logger.info(f"✓ {len(connected_devices)}개의 Android 기기가 연결되어 있습니다.")
            for device in connected_devices:
                logger.info(f"  - {device}")
            return True
            
        except FileNotFoundError:
            logger.error("ADB를 찾을 수 없습니다.")
            return False
        except Exception as e:
            logger.error(f"ADB 연결 확인 중 오류: {e}")
            logger.error(f"오류 상세: {result.stdout if 'result' in locals() else 'N/A'}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def get_airplane_mode_status(self):
        """
        휴대폰의 현재 비행기 모드 상태 확인
        
        Returns:
            bool: 비행기 모드가 켜져 있으면 True, 꺼져 있으면 False, 확인 실패 시 None
        """
        try:
            result = self.run_command('shell', 'settings', 'get', 'global', 'airplane_mode_on')
            
            if result.returncode == 0:
                status = result.stdout.strip()
                is_on = (status == '1')
                logger.info(f"현재 비행기 모드 상태: {'켜짐' if is_on else '꺼짐'} ({status})")
                return is_on
            else:
                logger.warning(f"비행기 모드 상태 확인 실패: {result.stderr}")
                return None
        except Exception as e:
            logger.error(f"비행기 모드 상태 확인 중 오류: {e}")
            return None
# 전역 인스턴스 (싱글톤 패턴)
_adb_manager = None


def get_adb_manager(project_dir=None):
    """
    ADB Manager 싱글톤 인스턴스 반환
    
    Args:
        project_dir: ADB를 저장할 프로젝트 디렉토리
        
    Returns:
        ADBManager: ADB 관리자 인스턴스
    """
    global _adb_manager
    if _adb_manager is None:
        _adb_manager = ADBManager(project_dir)
    return _adb_manager


# 편의 함수들
def find_adb():
    """ADB 경로 찾기 또는 다운로드"""
    return get_adb_manager().find_or_download()


def run_adb_command(*args, timeout=10):
    """ADB 명령 실행"""
    return get_adb_manager().run_command(*args, timeout=timeout)


def check_adb_connection():
    """ADB 연결 확인"""
    return get_adb_manager().check_connection()


# 테스트 코드
if __name__ == '__main__':
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 60)
    print("ADB Manager 테스트")
    print("=" * 60)
    
    # ADB 찾기 또는 다운로드
    adb_path = find_adb()
    
    if adb_path:
        print(f"\n✓ ADB 준비 완료: {adb_path}")
        
        # 연결 확인
        print("\n연결된 기기 확인 중...")
        check_adb_connection()
    else:
        print("\n✗ ADB를 찾을 수 없습니다.")