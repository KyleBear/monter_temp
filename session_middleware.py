"""
세션 및 캐시 관리 미들웨어
각 요청 전에 세션과 캐시를 자동으로 정리하는 기능 제공
"""
from selenium.webdriver.remote.webdriver import WebDriver
import logging
import time
import requests
from test5 import get_adb_manager
import socket
from chrome_connection import open_chrome
import subprocess
logger = logging.getLogger(__name__)


class SessionMiddleware:
    """세션 및 캐시 관리 미들웨어 클래스"""
    
    def __init__(self, driver: WebDriver):
        """
        Args:
            driver: Selenium WebDriver 인스턴스
        """
        self.driver = driver
    
    def clear_session(self):
        """세션 스토리지 삭제"""
        try:
            # 현재 URL이 유효한지 확인 (data: URL이 아닌지)
            current_url = self.driver.current_url
            if current_url and not current_url.startswith('data:'):
                self.driver.execute_script("window.sessionStorage.clear();")
                logger.debug("세션 스토리지 삭제 완료")
            else:
                logger.debug("페이지가 로드되지 않아 세션 스토리지 삭제 건너뜀")
        except Exception as e:
            logger.warning(f"세션 스토리지 삭제 중 오류: {e}")
    
    def clear_cache(self):
        """캐시 및 로컬 스토리지 삭제"""
        try:
            # 현재 URL이 유효한지 확인
            current_url = self.driver.current_url
            if current_url and not current_url.startswith('data:'):
                # 로컬 스토리지 삭제
                self.driver.execute_script("window.localStorage.clear();")
                # IndexedDB 삭제 (가능한 경우)
                self.driver.execute_script("""
                    if (window.indexedDB) {
                        indexedDB.databases().then(databases => {
                            databases.forEach(db => {
                                indexedDB.deleteDatabase(db.name);
                            });
                        });
                    }
                """)
                logger.debug("캐시 및 로컬 스토리지 삭제 완료")
            else:
                logger.debug("페이지가 로드되지 않아 캐시 삭제 건너뜀")
        except Exception as e:
            logger.warning(f"캐시 삭제 중 오류: {e}")
    
    def clear_cookies(self):
        """쿠키 삭제"""
        try:
            self.driver.delete_all_cookies()
            logger.debug("쿠키 삭제 완료")
        except Exception as e:
            logger.warning(f"쿠키 삭제 중 오류: {e}")
    
    def clear_all(self):
        """세션, 캐시, 쿠키 모두 삭제 - 페이지가 로드된 후에만 스토리지 삭제"""
        self.clear_cookies()
        # 쿠키는 항상 삭제 가능
        
        # 페이지가 로드된 후에만 스토리지 삭제
        try:
            current_url = self.driver.current_url
            if current_url and not current_url.startswith('data:'):
                self.clear_cache()
                self.clear_session()
                logger.info("세션 및 캐시 전체 삭제 완료")
            else:
                logger.info("쿠키 삭제 완료 (페이지 미로드로 스토리지 삭제 건너뜀)")
        except Exception as e:
            logger.warning(f"스토리지 삭제 중 오류: {e}")

    def verify_clear(self):
        """세션 및 캐시 삭제 확인"""
        try:
            current_url = self.driver.current_url
            if current_url and not current_url.startswith('data:'):
                # 쿠키 확인
                cookies = self.driver.get_cookies()
                cookie_count = len(cookies)
                
                # 스토리지 확인
                local_storage = self.driver.execute_script("return Object.keys(localStorage).length;")
                session_storage = self.driver.execute_script("return Object.keys(sessionStorage).length;")
                
                logger.info(f"삭제 확인 - 쿠키: {cookie_count}개, 로컬스토리지: {local_storage}개, 세션스토리지: {session_storage}개")
                
                if cookie_count == 0 and local_storage == 0 and session_storage == 0:
                    logger.info("✓ 세션 및 캐시가 모두 삭제되었습니다")
                    return True
                else:
                    logger.warning(f"⚠ 일부 데이터가 남아있습니다 (쿠키:{cookie_count}, 로컬:{local_storage}, 세션:{session_storage})")
                    return False
            else:
                logger.debug("페이지가 로드되지 않아 확인 불가")
                return None
        except Exception as e:
            logger.warning(f"삭제 확인 중 오류: {e}")
            return None    

    def process(self, func, *args, **kwargs):
        """
        미들웨어 패턴: 함수 실행 전에 세션/캐시 정리
        
        Args:
            func: 실행할 함수
            *args, **kwargs: 함수에 전달할 인자
        
        Returns:
            함수 실행 결과
        """
        # 실행 전 세션 및 캐시 정리
        self.clear_all()
        
        # 함수 실행
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            logger.error(f"함수 실행 중 오류: {e}")
            raise


# ============================================================================
# Android Chrome 세션 관리 함수
# ============================================================================

def clear_android_chrome_session(port=9222, adb=None):
    """
    Android Chrome 세션 완전 정리
    - 포트를 사용하는 프로세스 종료
    - Chrome 프로세스 종료
    - ADB 포트 포워딩 제거 및 재설정
    - Chrome 재시작
    
    Args:
        port: 포트 번호 (기본값: 9222)
        adb: ADB Manager 인스턴스 (None이면 자동으로 가져옴)
    
    Returns:
        bool: 성공 여부
    """
    logger.info(f"[Android Chrome 세션 정리] 포트 {port} 세션 정리 시작...")
    try:
        if adb is None:
            adb = get_adb_manager()
        
        # 0. 포트를 사용하는 프로세스 종료 (Windows에서 포트 점유 문제 해결)
        try:
            from port_manager import PortManager
            port_manager = PortManager()
            logger.info(f"[Android Chrome 세션 정리] 포트 {port} 해제 중...")
            results = port_manager.free_ports([port], force=True, wait_time=2)
            if results.get(port, False):
                logger.info(f"✓ [Android Chrome 세션 정리] 포트 {port} 해제 완료")
            else:
                logger.warning(f"[Android Chrome 세션 정리] 포트 {port} 해제 실패")
        except Exception as e:
            logger.warning(f"[Android Chrome 세션 정리] 포트 해제 중 오류: {e}")
        
        # 1. Chrome 프로세스 완전 종료
        logger.info(f"[Android Chrome 세션 정리] Chrome 프로세스 종료 중...")
        for close_try in range(3):
            try:
                adb.run_command('shell', 'am', 'force-stop', 'com.android.chrome', timeout=3)
                time.sleep(1)
            except:
                pass
        
        # Chrome 프로세스 완전 종료 확인
        time.sleep(1)
        result = adb.run_command('shell', 'ps', '-A', timeout=3)
        if result.returncode == 0:
            chrome_found = False
            for line in result.stdout.strip().split('\n'):
                if 'com.android.chrome' in line:
                    chrome_found = True
                    logger.warning(f"[Android Chrome 세션 정리] Chrome 프로세스가 아직 실행 중입니다. 추가 종료 시도...")
                    try:
                        adb.run_command('shell', 'am', 'force-stop', 'com.android.chrome', timeout=3)
                        time.sleep(2)
                    except:
                        pass
                    break
            
            if not chrome_found:
                logger.info(f"✓ [Android Chrome 세션 정리] Chrome 프로세스 완전 종료 확인됨")
        
        # 2. ADB 포트 포워딩 제거
        logger.info(f"[Android Chrome 세션 정리] ADB 포트 포워딩 제거 중... (포트: {port})")
        try:
            result = adb.run_command('forward', '--list', timeout=3)
            if result.returncode == 0:
                forward_list = result.stdout.strip()
                if f'tcp:{port}' in forward_list:
                    for attempt in range(3):
                        try:
                            remove_result = adb.run_command('forward', '--remove', f'tcp:{port}', timeout=3)
                            if remove_result.returncode == 0:
                                logger.info(f"✓ [Android Chrome 세션 정리] 포트 {port}의 ADB 포워딩 제거 완료")
                                break
                        except subprocess.TimeoutExpired as e:
                            logger.warning(f"[Android Chrome 세션 정리] 포트 {port}의 ADB 포워딩 제거 중 타임아웃 (시도: {attempt + 1}/3): {e}")
                            if attempt < 2:
                                time.sleep(1)
                        except Exception as e:
                            logger.debug(f"[Android Chrome 세션 정리] 포트 {port}의 ADB 포워딩 제거 시도 {attempt + 1}/3 실패: {e}")
                            if attempt < 2:
                                time.sleep(1)
        except Exception as e:
            logger.warning(f"[Android Chrome 세션 정리] ADB 포워딩 제거 중 오류: {e}")
        
        time.sleep(1)  # 포워딩 제거 후 대기
        
        logger.info(f"[Android Chrome 세션 정리] 포트 {port} 세션 정리 완료")
        return True
        
    except Exception as e:
        logger.error(f"[Android Chrome 세션 정리] 포트 {port} 세션 정리 중 오류: {e}", exc_info=True)
        return False


def restart_android_chrome(port=9222, adb=None):
    """
    Android Chrome 재시작 및 포트 포워딩 재설정
    
    Args:
        port: 포트 번호 (기본값: 9222)
        adb: ADB Manager 인스턴스 (None이면 자동으로 가져옴)
    
    Returns:
        bool: 성공 여부
    """
    logger.info(f"[Android Chrome 재시작] 포트 {port} Chrome 재시작 시작...")
    try:
        if adb is None:
            from test5 import get_adb_manager
            adb = get_adb_manager()
        
        # 1. 포트 포워딩 재설정
        logger.info(f"[Android Chrome 재시작] 포트 포워딩 재설정 중... (포트: {port})")
        from test5 import setup_port_forwarding
        if not setup_port_forwarding(adb, port):
            logger.error(f"[Android Chrome 재시작] 포트 포워딩 설정 실패 (포트: {port})")
            return False
        
        # 2. Chrome 시작
        logger.info(f"[Android Chrome 재시작] Chrome 시작 중...")

        if not open_chrome():
            logger.error(f"[Android Chrome 재시작] Chrome 시작 실패")
            return False
        time.sleep(4)
        # 3. Chrome DevTools 준비 확인
        logger.info(f"[Android Chrome 재시작] Chrome DevTools 준비 대기 중... (포트: {port})")
        import time
        import requests
        
        time.sleep(5)  # Chrome 시작 후 대기
        
        chrome_ready = False
        last_error = None
        last_targets_info = None
        
        for check_retry in range(15):
            try:
                response = requests.get(f'http://127.0.0.1:{port}/json', timeout=2)
                if response.status_code == 200:
                    targets = response.json()
                    target_types = [t.get('type') for t in targets] if targets else []
                    last_targets_info = f"타겟 수: {len(targets) if targets else 0}, 타입: {target_types}"
                    
                    logger.debug(f"[Android Chrome 재시작] DevTools 확인 시도 {check_retry + 1}/15: {last_targets_info}")
                    
                    if targets and len(targets) > 0:
                        has_page_target = any(t.get('type') == 'page' for t in targets)
                        if has_page_target:
                            chrome_ready = True
                            logger.info(f"✓ [Android Chrome 재시작] Chrome DevTools 준비 완료 (포트: {port})")
                            break
                    else:
                        last_error = "타겟이 없습니다"
                else:
                    last_error = f"HTTP {response.status_code}"
                    logger.debug(f"[Android Chrome 재시작] DevTools HTTP 응답 코드: {response.status_code}")
            except requests.exceptions.Timeout:
                last_error = "요청 타임아웃"
                logger.debug(f"[Android Chrome 재시작] DevTools 확인 시도 {check_retry + 1}/15: 타임아웃")
            except requests.exceptions.ConnectionError as e:
                last_error = f"연결 오류: {str(e)}"
                logger.debug(f"[Android Chrome 재시작] DevTools 확인 시도 {check_retry + 1}/15: 연결 실패")
            except Exception as e:
                last_error = f"예외: {str(e)}"
                logger.debug(f"[Android Chrome 재시작] DevTools 확인 시도 {check_retry + 1}/15 실패: {e}")
            
            if check_retry < 14:
                time.sleep(1)
        
        if not chrome_ready:
            logger.error(f"[Android Chrome 재시작] Chrome DevTools 준비 확인 실패 (포트: {port})")
            logger.error(f"[Android Chrome 재시작] 마지막 오류: {last_error}")
            logger.error(f"[Android Chrome 재시작] 마지막 타겟 정보: {last_targets_info}")
            logger.error(f"[Android Chrome 재시작] 15번 재시도 후에도 'page' 타입 타겟을 찾을 수 없습니다.")
            return False
        
        logger.info(f"[Android Chrome 재시작] 포트 {port} Chrome 재시작 완료")
        return True
        
    except Exception as e:
        logger.error(f"[Android Chrome 재시작] 포트 {port} Chrome 재시작 중 오류: {e}", exc_info=True)
        return False


def ensure_android_chrome_session(port=9222, adb=None):
    """
    Android Chrome 세션 보장 (정리 후 재시작)
    
    Args:
        port: 포트 번호 (기본값: 9222)
        adb: ADB Manager 인스턴스 (None이면 자동으로 가져옴)
    
    Returns:
        bool: 성공 여부
    """
    logger.info(f"[Android Chrome 세션 보장] 포트 {port} 세션 보장 시작...")
    
    # 1. 기존 세션 정리
    if not clear_android_chrome_session(port, adb):
        logger.warning(f"[Android Chrome 세션 보장] 세션 정리 실패했지만 계속 진행합니다...")
    
    # 2. Chrome 재시작
    if not restart_android_chrome(port, adb):
        logger.error(f"[Android Chrome 세션 보장] Chrome 재시작 실패 (포트: {port})")
        return False
    
    logger.info(f"✓ [Android Chrome 세션 보장] 포트 {port} 세션 보장 완료")
    return True


def check_android_chrome_session(port=9222):
    """
    Android Chrome 세션 상태 확인
    
    Args:
        port: 포트 번호 (기본값: 9222)
        클라이언스 소켓연결을 끊고, 포트 점유를 해제 해야함.
    Returns:
        dict: 세션 상태 정보
        {
            'chrome_running': bool,
            'port_forwarding': bool,
            'devtools_ready': bool,
            'targets_count': int
        }
    """
    logger.info(f"[Android Chrome 세션 확인] 포트 {port} 세션 상태 확인 중...")
    
    result = {
        'chrome_running': False,
        'port_forwarding': False,
        'devtools_ready': False,
        'targets_count': 0
    }
    
    try:
        # 1. Chrome 프로세스 확인
        adb = get_adb_manager()
        
        process_result = adb.run_command('shell', 'ps', '-A', timeout=3)
        if process_result.returncode == 0:
            for line in process_result.stdout.strip().split('\n'):
                if 'com.android.chrome' in line:
                    result['chrome_running'] = True
                    break
        
        # 2. 포트 포워딩 확인
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        port_result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        result['port_forwarding'] = (port_result == 0)

        # 2. 기본 포트 -> ADB 포트 포워딩 확인
        try:
            forward_result = adb.run_command('forward', '--list', timeout=3)
            if forward_result.returncode == 0:
                forward_list = forward_result.stdout.strip()
                result['port_forwarding'] = f'tcp:{port}' in forward_list
            else:
                result['port_forwarding'] = False
        except Exception as e:
            logger.warning(f"[Android Chrome 세션 확인] ADB 포워딩 확인 중 오류: {e}") 
        # 3. Chrome DevTools 확인
        if result['port_forwarding']:
            try:
                response = requests.get(f'http://127.0.0.1:{port}/json', timeout=2)
                if response.status_code == 200:
                    targets = response.json()
                    if targets:
                        result['targets_count'] = len(targets)
                        result['devtools_ready'] = any(t.get('type') == 'page' for t in targets)
            except:
                pass
        
        logger.info(f"[Android Chrome 세션 확인] 결과 - Chrome 실행: {result['chrome_running']}, "
                   f"포트 포워딩: {result['port_forwarding']}, "
                   f"DevTools 준비: {result['devtools_ready']}, "
                   f"타겟 수: {result['targets_count']}")
# 348-353줄 수정 (ADB 포워딩 직접 확인)

            # 폴백: 소켓 연결로 확인 -> 걍 오류 띄움
            # try:
            #     sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            #     sock.settimeout(1)
            #     port_result = sock.connect_ex(('127.0.0.1', port))
            #     sock.close()
            #     result['port_forwarding'] = (port_result == 0)
            # except:
            #     result['port_forwarding'] = False
        
    except Exception as e:
        logger.error(f"[Android Chrome 세션 확인] 오류: {e}", exc_info=True)
    
    return result

