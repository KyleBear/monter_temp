"""
Android Chrome 순차 실행 버전 (test7.py 기반)
Android Chrome에서는 여러 탭을 열어도, 백그라운드에서 DevTools로 각각을 제어하는 병렬 크롤링은 불가능하다.
모든 탭이 단일 WebView 기반 "chrome_devtools_remote" 세션 하나를 공유함. (단일 세션 기반)
따라서 순차 실행으로 변경하고, 쓰레드 락이 필요 없음.
"""
import time
import logging
import random
import socket
import requests
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from config import Config
from test5 import create_click_result_script, setup_port_forwarding
from test6 import DataConnectionManager
from adb_manager import get_adb_manager
import pandas as pd
from bs4 import BeautifulSoup
from chrome_connection import restart_chrome, close_chrome, open_chrome
import os
import shutil
import threading
import sys
from session_middleware import check_android_chrome_session
from test5 import get_adb_manager
from test5 import setup_port_forwarding
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# ============================================================================
# Android Chrome 세션 관리 함수
# ============================================================================

def clear_android_chrome_session(port=9222, adb=None):
    """
    Android Chrome 세션 완전 정리
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
                        except:
                            pass
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

            adb = get_adb_manager()
        
        # 1. 포트 포워딩 재설정
        logger.info(f"[Android Chrome 재시작] 포트 포워딩 재설정 중... (포트: {port})")

        if not setup_port_forwarding(adb, port):
            logger.error(f"[Android Chrome 재시작] 포트 포워딩 설정 실패 (포트: {port})")
            return False
        
        # 2. Chrome 시작
        logger.info(f"[Android Chrome 재시작] Chrome 시작 중...")

        if not open_chrome():
            logger.error(f"[Android Chrome 재시작] Chrome 시작 실패")
            return False
        
        # Chrome이 완전히 시작되고 m.naver.com이 로드될 때까지 충분한 대기
        logger.info(f"[Android Chrome 재시작] Chrome 및 페이지 로딩 대기 중... (8초)")
        time.sleep(8)  # 5초 -> 8초로 증가
        
        # 3. Chrome DevTools 준비 확인
        logger.info(f"[Android Chrome 재시작] Chrome DevTools 준비 대기 중... (포트: {port})")

        
        time.sleep(5)  # Chrome 시작 후 대기
        
        chrome_ready = False
        for check_retry in range(15):
            try:
                response = requests.get(f'http://127.0.0.1:{port}/json', timeout=2)
                if response.status_code == 200:
                    targets = response.json()
                    if targets and len(targets) > 0:
                        has_page_target = any(t.get('type') == 'page' for t in targets)
                        if has_page_target:
                            chrome_ready = True
                            logger.info(f"✓ [Android Chrome 재시작] Chrome DevTools 준비 완료 (포트: {port})")
                            break
            except:
                pass
            if check_retry < 14:
                time.sleep(1)
        
        if not chrome_ready:
            logger.warning(f"[Android Chrome 재시작] Chrome DevTools 준비 확인 실패 (포트: {port})")
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
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        port_result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        result['port_forwarding'] = (port_result == 0)
        
        # 3. Chrome DevTools 확인
        if result['port_forwarding']:
            import requests
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
        
    except Exception as e:
        logger.error(f"[Android Chrome 세션 확인] 오류: {e}", exc_info=True)
    
    return result


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 단일 포트 사용 (순차 실행이므로 하나만 필요)
PORT = 9222


def ensure_chromedriver_138(port):
    """
    ChromeDriver 138 버전을 미리 다운로드
    
    Args:
        port: 포트 번호 (로깅용)
    
    Returns:
        Service: ChromeDriver Service 객체
    """
    logger.info(f"[ensure_chromedriver_138] 함수 시작 (포트: {port})")
    logger.info(f"[ensure_chromedriver_138] 모듈 import 시작 (포트: {port})")

    logger.info(f"[ensure_chromedriver_138] 모듈 import 완료 (포트: {port})")
    
    # win64 버전을 강제로 선택하기 위한 커스텀 ChromeDriverManager
    logger.info(f"[ensure_chromedriver_138] Win64ChromeDriverManager 클래스 정의 시작 (포트: {port})")
    class Win64ChromeDriverManager(ChromeDriverManager):
        def get_os_type(self):
            os_type = super().get_os_type()
            if "win" in os_type.lower() or os_type == "win32":
                return "win64"
            return os_type
    logger.info(f"[ensure_chromedriver_138] Win64ChromeDriverManager 클래스 정의 완료 (포트: {port})")
    
    # Chrome 138 버전 명시적으로 지정 (휴대폰 Chrome 버전)
    logger.info(f"[ensure_chromedriver_138] Win64ChromeDriverManager 인스턴스 생성 시작 (포트: {port})")
    manager = Win64ChromeDriverManager(driver_version="138")
    logger.info(f"[ensure_chromedriver_138] Win64ChromeDriverManager 인스턴스 생성 완료 (포트: {port})")
    
    # manager.install() 실행
    logger.info(f"[포트 {port}] Chrome 138 버전의 ChromeDriver를 미리 다운로드합니다...")
    logger.info(f"[ensure_chromedriver_138] manager.install() 호출 시작 (포트: {port})")
    driver_path = manager.install()
    logger.info(f"[ensure_chromedriver_138] manager.install() 호출 완료 (포트: {port})")
    logger.info(f"[포트 {port}] ChromeDriver 다운로드 완료: {driver_path}")
    
    # ChromeDriver 경로 찾기와 Service 생성
    logger.info(f"[ensure_chromedriver_138] ChromeDriver 경로 찾기 시작 (포트: {port})")
    logger.info(f"[ensure_chromedriver_138] driver_path: {driver_path} (포트: {port})")
    logger.info(f"[ensure_chromedriver_138] os.path.isfile(driver_path): {os.path.isfile(driver_path)} (포트: {port})")
    logger.info(f"[ensure_chromedriver_138] os.path.isdir(driver_path): {os.path.isdir(driver_path) if os.path.exists(driver_path) else False} (포트: {port})")
    
    try:
        service = None
        if os.path.isfile(driver_path):
            logger.info(f"[ensure_chromedriver_138] driver_path는 파일입니다 (포트: {port})")
            if driver_path.endswith('chromedriver.exe') or driver_path.endswith('chromedriver'):
                logger.info(f"[ensure_chromedriver_138] chromedriver.exe 파일 직접 사용 (포트: {port})")
                service = Service(driver_path)
                service.service_args = ['--timeout=5000']
                logger.info(f"[ensure_chromedriver_138] Service 객체 생성 완료 (포트: {port})")
            else:
                # 디렉토리인 경우 chromedriver.exe 찾기
                logger.info(f"[ensure_chromedriver_138] 파일이지만 chromedriver.exe가 아님, 디렉토리에서 검색 (포트: {port})")
                search_path = driver_path if os.path.isdir(driver_path) else os.path.dirname(driver_path)
                logger.info(f"[ensure_chromedriver_138] 검색 경로: {search_path} (포트: {port})")
                driver_found = False
                for root, dirs, files in os.walk(search_path):
                    for file in files:
                        if file == 'chromedriver.exe' and 'win64' in root:
                            service = Service(os.path.join(root, file))
                            service.service_args = ['--timeout=5000']
                            driver_found = True
                            logger.info(f"[포트 {port}] ChromeDriver 찾음: {os.path.join(root, file)}")
                            break
                    if driver_found:
                        break
                if not driver_found:
                    logger.warning(f"[ensure_chromedriver_138] chromedriver.exe를 찾지 못함, driver_path 직접 사용 (포트: {port})")
                    service = Service(driver_path)
                    service.service_args = ['--timeout=5000']
        else:
            # 디렉토리인 경우
            logger.info(f"[ensure_chromedriver_138] driver_path는 디렉토리입니다 (포트: {port})")
            search_path = driver_path
            driver_found = False
            logger.info(f"[ensure_chromedriver_138] 디렉토리 검색 시작: {search_path} (포트: {port})")
            for root, dirs, files in os.walk(search_path):
                for file in files:
                    if file == 'chromedriver.exe' and 'win64' in root:
                        service = Service(os.path.join(root, file))
                        service.service_args = ['--timeout=5000']
                        driver_found = True
                        logger.info(f"[포트 {port}] ChromeDriver 찾음: {os.path.join(root, file)}")
                        break
                if driver_found:
                    break
            if not driver_found:
                logger.warning(f"[ensure_chromedriver_138] ChromeDriver를 찾을 수 없어 기본 경로를 사용합니다 (포트: {port})")
                service = Service()
                service.service_args = ['--timeout=5000']
        
        logger.info(f"[ensure_chromedriver_138] Service 객체 생성 완료: {service} (포트: {port})")
    except Exception as e:
        logger.error(f"[ensure_chromedriver_138] ChromeDriver Service 생성 실패 (포트: {port}): {e}", exc_info=True)
        raise
    
    logger.info(f"[ensure_chromedriver_138] 함수 종료 (포트: {port})")
    return service


class StealthNaverCrawler:
    """봇 탐지 회피 기능이 강화된 네이버 크롤러"""
    
    def __init__(self, port=9222):
        logger.info(f"[StealthNaverCrawler] 초기화 시작 (포트: {port})")
        self.driver = None
        self.port = port
        try:
            self._setup_stealth_driver()
            logger.info(f"[StealthNaverCrawler] 초기화 완료 (포트: {port})")
        except Exception as e:
            logger.error(f"[StealthNaverCrawler] 초기화 실패 (포트: {port}): {e}", exc_info=True)
            raise
    
    # def _clear_port_session(self, port):
    #     """포트 세션 점유 해제 (Chrome 프로세스는 종료하지 않음, 포트 포워딩도 유지)"""
    #     logger.info(f"[포트 세션 정리] 포트 {port} 세션 정리 시작...")
    #     # Chrome은 이미 test_single_iteration_stealth에서 시작되었으므로 여기서는 정리하지 않음
    #     logger.info(f"[포트 세션 정리] 포트 {port} 세션 정리 완료 (Chrome과 포트 포워딩은 유지)")
    #     return True
    
    def _setup_stealth_driver(self):
        """스텔스 드라이버 설정"""
        logger.info(f"[_setup_stealth_driver] 시작 (포트: {self.port})")
        
        # 원격 디버깅 모드에서는 일반 Selenium WebDriver 사용
        logger.info(f"[_setup_stealth_driver] 모듈 import 중...")
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        from selenium import webdriver
        logger.info(f"[_setup_stealth_driver] 모듈 import 완료")
        
        logger.info(f"[_setup_stealth_driver] ChromeOptions 생성 중...")
        options = ChromeOptions()
        logger.info(f"[_setup_stealth_driver] ChromeOptions 생성 완료")
        
        # 모바일 Chrome 원격 디버깅
        logger.info(f"[_setup_stealth_driver] debuggerAddress 설정 중... (포트: {self.port})")
        options.add_experimental_option("debuggerAddress", f"127.0.0.1:{self.port}")
        logger.info(f"[_setup_stealth_driver] debuggerAddress 설정 완료: 127.0.0.1:{self.port}")
        
        # ChromeDriver Service 준비
        logger.info(f"[_setup_stealth_driver] ChromeDriver Service 준비 중... (포트: {self.port})")
        try:
            logger.info(f"[_setup_stealth_driver] ensure_chromedriver_138 호출 중... (포트: {self.port})")
            service = ensure_chromedriver_138(self.port)
            logger.info(f"[_setup_stealth_driver] ensure_chromedriver_138 완료 (포트: {self.port})")
            logger.info(f"[_setup_stealth_driver] service.service_args 설정 중... (포트: {self.port})")
            service.service_args = ['--timeout=5000']  # 5초 타임아웃
            logger.info(f"[_setup_stealth_driver] service.service_args 설정 완료 (포트: {self.port})")
        except Exception as e:
            logger.error(f"[_setup_stealth_driver] ChromeDriver 준비 실패 (포트: {self.port}): {e}", exc_info=True)
            raise
        
        # 드라이버 생성
        logger.info(f"[_setup_stealth_driver] 드라이버 생성 단계 시작 (포트: {self.port})")
        try:
            logger.info(f"[_setup_stealth_driver] [1단계] 드라이버 생성 시작 (포트: {self.port})")
            
            # 연결 전 Chrome DevTools 준비 상태 재확인 소켓 9222 포트 연결 확인
            logger.info(f"[_setup_stealth_driver] [2단계] Chrome DevTools 준비 상태 확인 시작 (포트: {self.port})")

            chrome_ready = False
            for check_attempt in range(5):  # 최대 5번 확인
                logger.debug(f"[_setup_stealth_driver] Chrome DevTools 확인 시도 {check_attempt + 1}/5 (포트: {self.port})")
                try:
                    # 세션 상태 확인 (소켓 직접 사용 대신)

                    session_status = check_android_chrome_session(self.port)
                    
                    if session_status['port_forwarding'] and session_status['devtools_ready']:
                        chrome_ready = True
                        logger.info(f"[_setup_stealth_driver] Chrome DevTools 준비 확인됨 (포트: {self.port})")
                        logger.debug(f"[_setup_stealth_driver] 타겟 수: {session_status['targets_count']}개 (포트: {self.port})")
                        break
                    else:
                        logger.debug(f"[_setup_stealth_driver] Chrome 세션 상태 - "
                                   f"Chrome 실행: {session_status['chrome_running']}, "
                                   f"포트 포워딩: {session_status['port_forwarding']}, "
                                   f"DevTools 준비: {session_status['devtools_ready']} (포트: {self.port})")
                    
                    if check_attempt < 4:
                        time.sleep(0.5)
                except Exception as e:
                    logger.debug(f"[_setup_stealth_driver] 세션 확인 중 오류: {e} (포트: {self.port})")
                    if check_attempt < 4:
                        time.sleep(0.5)
            
            if not chrome_ready:
                logger.error(f"[_setup_stealth_driver] Chrome DevTools 준비 확인 실패 (포트: {self.port})")
                logger.error(f"[_setup_stealth_driver] 최종 세션 상태: {session_status}")
                
                # 타겟이 없을 때 Chrome 재시작 시도
                logger.info(f"[_setup_stealth_driver] 타겟이 없어 Chrome 재시작 시도 중... (포트: {self.port})")
                if ensure_android_chrome_session(self.port):
                    # 재시작 후 다시 확인
                    logger.info(f"[_setup_stealth_driver] Chrome 재시작 완료, DevTools 준비 확인 중... (포트: {self.port})")
                    time.sleep(5)  # 재시작 후 대기
                    
                    # 재시작 후 최종 확인 (최대 15초)
                    chrome_ready = False
                    for retry_check in range(15):
                        session_status = check_android_chrome_session(self.port)
                        logger.info(f"[_setup_stealth_driver] 재시작 후 확인 시도 {retry_check + 1}/15: "
                                   f"포트 포워딩={session_status['port_forwarding']}, "
                                   f"DevTools 준비={session_status['devtools_ready']}, "
                                   f"타겟 수={session_status['targets_count']}")
                        
                        if session_status['port_forwarding'] and session_status['devtools_ready']:
                            chrome_ready = True
                            logger.info(f"[_setup_stealth_driver] ✓ Chrome 재시작 후 DevTools 준비 완료 (포트: {self.port}, 타겟 수: {session_status['targets_count']})")
                            break
                        
                        if retry_check < 14:
                            time.sleep(1)
                    
                    if not chrome_ready:
                        logger.error(f"[_setup_stealth_driver] Chrome 재시작 후에도 DevTools 준비 실패 (포트: {self.port})")
                        logger.error(f"[_setup_stealth_driver] 최종 세션 상태: {session_status}")
                        raise Exception(f"Chrome DevTools 준비 실패 (포트: {self.port}): 타겟이 없습니다. "
                                      f"세션 상태: {session_status}")
                else:
                    logger.error(f"[_setup_stealth_driver] Chrome 재시작 실패 (포트: {self.port})")
                    raise Exception(f"Chrome 재시작 실패 (포트: {self.port})")
            else:
                time.sleep(1)  # 준비 완료 후 짧은 안정화 대기
            
            # WebDriver 생성 전 Chrome 재시작하여 새 타겟 생성 (Android Chrome 연결 문제 해결)
            logger.info(f"[_setup_stealth_driver] WebDriver 생성 전 Chrome 재시작하여 새 타겟 생성 중... (포트: {self.port})")
            try:
                from session_middleware import ensure_android_chrome_session
                if ensure_android_chrome_session(self.port):
                    logger.info(f"[_setup_stealth_driver] ✓ Chrome 재시작 완료, 새 타겟 생성됨 (포트: {self.port})")
                    time.sleep(5)  # 재시작 후 대기
                    
                    # 재시작 후 타겟 확인
                    session_status = check_android_chrome_session(self.port)
                    if not (session_status['port_forwarding'] and session_status['devtools_ready']):
                        logger.warning(f"[_setup_stealth_driver] 재시작 후에도 DevTools 준비 실패 (포트: {self.port})")
                        raise Exception(f"Chrome 재시작 후 DevTools 준비 실패 (포트: {self.port})")
                else:
                    logger.warning(f"[_setup_stealth_driver] Chrome 재시작 실패했지만 계속 진행 (포트: {self.port})")
            except Exception as e:
                logger.warning(f"[_setup_stealth_driver] Chrome 재시작 중 오류 (계속 진행): {e}")
            
            # WebDriver 생성 전 타겟 타입 최종 확인
            logger.info(f"[_setup_stealth_driver] WebDriver 생성 전 타겟 타입 최종 확인 중... (포트: {self.port})")
            
            # 먼저 세션 상태 재확인 (포트 포워딩 및 DevTools 준비 상태)
            session_status = check_android_chrome_session(self.port)
            logger.info(f"[_setup_stealth_driver] 세션 상태 재확인: 포트 포워딩={session_status['port_forwarding']}, "
                       f"DevTools 준비={session_status['devtools_ready']}, "
                       f"Chrome 실행={session_status['chrome_running']}, "
                       f"타겟 수={session_status['targets_count']}")
            
            # 포트 포워딩이 없으면 재설정
            if not session_status['port_forwarding']:
                logger.warning(f"[_setup_stealth_driver] 포트 포워딩이 없습니다. 재설정 시도 중... (포트: {self.port})")
                try:
                    from test5 import get_adb_manager, setup_port_forwarding
                    adb = get_adb_manager()
                    if not adb.check_connection():
                        logger.error(f"[_setup_stealth_driver] ADB 연결이 끊어졌습니다. (포트: {self.port})")
                        raise Exception(f"ADB 연결이 끊어졌습니다 (포트: {self.port})")
                    
                    if setup_port_forwarding(adb, self.port):
                        logger.info(f"[_setup_stealth_driver] ✓ 포트 포워딩 재설정 완료 (포트: {self.port})")
                        time.sleep(2)  # 포트 포워딩 안정화 대기
                        session_status = check_android_chrome_session(self.port)
                    else:
                        logger.error(f"[_setup_stealth_driver] 포트 포워딩 재설정 실패 (포트: {self.port})")
                        raise Exception(f"포트 포워딩 재설정 실패 (포트: {self.port})")
                except Exception as e:
                    logger.error(f"[_setup_stealth_driver] 포트 포워딩 재설정 중 오류: {e}")
                    raise Exception(f"포트 포워딩 재설정 중 오류 (포트: {self.port}): {e}")
            
            # DevTools가 준비되지 않았으면 Chrome 재시작
            if not session_status['devtools_ready']:
                logger.warning(f"[_setup_stealth_driver] DevTools가 준비되지 않았습니다. Chrome 재시작 시도 중... (포트: {self.port})")
                try:
                    from session_middleware import ensure_android_chrome_session
                    if ensure_android_chrome_session(self.port):
                        logger.info(f"[_setup_stealth_driver] ✓ Chrome 재시작 완료 (포트: {self.port})")
                        time.sleep(3)  # 재시작 후 대기
                        session_status = check_android_chrome_session(self.port)
                        
                        if not session_status['devtools_ready']:
                            logger.error(f"[_setup_stealth_driver] Chrome 재시작 후에도 DevTools 준비 실패 (포트: {self.port})")
                            raise Exception(f"Chrome 재시작 후에도 DevTools 준비 실패 (포트: {self.port})")
                    else:
                        logger.error(f"[_setup_stealth_driver] Chrome 재시작 실패 (포트: {self.port})")
                        raise Exception(f"Chrome 재시작 실패 (포트: {self.port})")
                except Exception as e:
                    logger.error(f"[_setup_stealth_driver] Chrome 재시작 중 오류: {e}")
                    raise Exception(f"Chrome 재시작 중 오류 (포트: {self.port}): {e}")
            
            # 세션 상태 최종 확인
            if not (session_status['port_forwarding'] and session_status['devtools_ready']):
                logger.error(f"[_setup_stealth_driver] 세션 상태 불완전 (포트: {self.port}): {session_status}")
                raise Exception(f"세션 상태 불완전 (포트: {self.port}): 포트 포워딩={session_status['port_forwarding']}, DevTools 준비={session_status['devtools_ready']}")
            
            # 타겟 타입 최종 확인 (재시도 로직 포함)
            import requests
            max_retries = 3
            for retry in range(max_retries):
                try:
                    response = requests.get(f'http://127.0.0.1:{self.port}/json', timeout=3)
                    if response.status_code == 200:
                        targets = response.json()
                        if targets:
                            target_types = [t.get('type') for t in targets]
                            target_info = []
                            for t in targets:
                                target_info.append({
                                    'type': t.get('type'),
                                    'title': t.get('title', 'N/A')[:50],
                                    'url': t.get('url', 'N/A')[:80],
                                    'id': t.get('id', 'N/A'),
                                    'webSocketDebuggerUrl': t.get('webSocketDebuggerUrl', 'N/A')[:100]
                                })
                            
                            logger.info(f"[_setup_stealth_driver] 타겟 상세 정보: {target_info}")
                            logger.info(f"[_setup_stealth_driver] 타겟 타입: {target_types}")
                            
                            page_targets = [t for t in targets if t.get('type') == 'page']
                            if not page_targets:
                                logger.error(f"[_setup_stealth_driver] 'page' 타입 타겟이 없습니다! (포트: {self.port})")
                                logger.error(f"[_setup_stealth_driver] 실제 타겟 타입: {target_types}")
                                raise Exception(f"Chrome DevTools 'page' 타입 타겟이 없습니다 (포트: {self.port}). "
                                              f"실제 타입: {target_types}")
                            
                            logger.info(f"[_setup_stealth_driver] ✓ 'page' 타입 타겟 확인됨: {len(page_targets)}개 (포트: {self.port})")
                            for pt in page_targets:
                                logger.info(f"[_setup_stealth_driver]   - 페이지 타겟: {pt.get('title', 'N/A')[:50]} ({pt.get('url', 'N/A')[:80]})")
                                logger.info(f"[_setup_stealth_driver]   - WebSocket URL: {pt.get('webSocketDebuggerUrl', 'N/A')[:100]}")
                            break  # 성공 시 루프 종료
                        else:
                            logger.error(f"[_setup_stealth_driver] 타겟 목록이 비어있습니다 (포트: {self.port})")
                            if retry < max_retries - 1:
                                logger.warning(f"[_setup_stealth_driver] 재시도 중... ({retry + 1}/{max_retries})")
                                time.sleep(2)
                            else:
                                raise Exception(f"Chrome DevTools 타겟이 없습니다 (포트: {self.port})")
                    else:
                        logger.error(f"[_setup_stealth_driver] DevTools API 접근 실패: HTTP {response.status_code} (포트: {self.port})")
                        if retry < max_retries - 1:
                            logger.warning(f"[_setup_stealth_driver] 재시도 중... ({retry + 1}/{max_retries})")
                            time.sleep(2)
                        else:
                            raise Exception(f"Chrome DevTools API 접근 실패: HTTP {response.status_code} (포트: {self.port})")
                except requests.exceptions.ConnectionError as e:
                    logger.error(f"[_setup_stealth_driver] DevTools API 연결 실패 (포트: {self.port}, 시도: {retry + 1}/{max_retries}): {e}")
                    if retry < max_retries - 1:
                        # 연결 실패 시 세션 재확인 및 재설정
                        logger.warning(f"[_setup_stealth_driver] 연결 실패로 인해 세션 재확인 중...")
                        session_status = check_android_chrome_session(self.port)
                        logger.warning(f"[_setup_stealth_driver] 현재 세션 상태: Chrome 실행={session_status['chrome_running']}, "
                                     f"포트 포워딩={session_status['port_forwarding']}, "
                                     f"DevTools 준비={session_status['devtools_ready']}, "
                                     f"타겟 수={session_status['targets_count']}")
                        
                        if not session_status['port_forwarding']:
                            logger.warning(f"[_setup_stealth_driver] 포트 포워딩이 없습니다. 재설정 시도 중...")
                            try:
                                from test5 import get_adb_manager, setup_port_forwarding
                                adb = get_adb_manager()
                                if not adb.check_connection():
                                    logger.error(f"[_setup_stealth_driver] ADB 연결이 끊어졌습니다!")
                                    raise Exception(f"ADB 연결이 끊어졌습니다 (포트: {self.port})")
                                if setup_port_forwarding(adb, self.port):
                                    logger.info(f"[_setup_stealth_driver] ✓ 포트 포워딩 재설정 완료")
                                else:
                                    logger.error(f"[_setup_stealth_driver] 포트 포워딩 재설정 실패")
                            except Exception as port_error:
                                logger.error(f"[_setup_stealth_driver] 포트 포워딩 재설정 중 오류: {port_error}")
                        
                        if not session_status['devtools_ready']:
                            logger.warning(f"[_setup_stealth_driver] DevTools가 준비되지 않았습니다. Chrome 재시작 시도 중...")
                            try:
                                from session_middleware import ensure_android_chrome_session
                                if ensure_android_chrome_session(self.port):
                                    logger.info(f"[_setup_stealth_driver] ✓ Chrome 재시작 완료")
                                    time.sleep(3)  # 재시작 후 대기
                                else:
                                    logger.error(f"[_setup_stealth_driver] Chrome 재시작 실패")
                            except Exception as chrome_error:
                                logger.error(f"[_setup_stealth_driver] Chrome 재시작 중 오류: {chrome_error}")
                        
                        time.sleep(2)
                    else:
                        # 최종 실패 시 상세한 상태 정보와 함께 예외 발생
                        final_status = check_android_chrome_session(self.port)
                        error_msg = (f"Chrome DevTools API 연결 실패 (포트: {self.port}): {e}\n"
                                   f"최종 세션 상태: Chrome 실행={final_status['chrome_running']}, "
                                   f"포트 포워딩={final_status['port_forwarding']}, "
                                   f"DevTools 준비={final_status['devtools_ready']}, "
                                   f"타겟 수={final_status['targets_count']}")
                        logger.error(f"[_setup_stealth_driver] {error_msg}")
                        raise Exception(error_msg)
                except Exception as e:
                    logger.error(f"[_setup_stealth_driver] 타겟 확인 중 오류 (포트: {self.port}): {e}")
                    if retry < max_retries - 1:
                        time.sleep(2)
                    else:
                        raise
            
            # 타임아웃 설정: threading과 강제 종료를 사용하여 확실한 타임아웃 적용
            logger.info(f"[_setup_stealth_driver] 드라이버 생성 스레드 준비 중... (포트: {self.port})")
            driver_result = {'driver': None, 'error': None, 'completed': False}
            driver_thread = None
            
            def driver_creation():
                logger.info(f"[driver_creation] 스레드 시작 (포트: {self.port})")
                try:
                    # WebDriver 생성 직전에 타겟 재확인 및 상태 확인
                    logger.info(f"[driver_creation] WebDriver 생성 직전 타겟 재확인 중... (포트: {self.port})")
                    import requests
                    try:
                        response = requests.get(f'http://127.0.0.1:{self.port}/json', timeout=2)
                        if response.status_code == 200:
                            targets = response.json()
                            page_targets = [t for t in targets if t.get('type') == 'page'] if targets else []
                            if not page_targets:
                                raise Exception(f"WebDriver 생성 직전 타겟 확인 실패: 'page' 타입 타겟이 없습니다 (포트: {self.port})")
                            
                            logger.info(f"[driver_creation] ✓ 타겟 재확인 완료: {len(page_targets)}개 'page' 타입 타겟 (포트: {self.port})")
                            
                            # 타겟 상세 정보 로깅
                            for pt in page_targets:
                                logger.info(f"[driver_creation]   - 타겟 ID: {pt.get('id')}, URL: {pt.get('url', 'N/A')[:80]}, "
                                          f"WebSocket: {pt.get('webSocketDebuggerUrl', 'N/A')[:80]}")
                            
                            # 타겟이 사용 가능한지 확인 (WebSocket 연결 테스트)
                            for pt in page_targets:
                                ws_url = pt.get('webSocketDebuggerUrl')
                                if ws_url:
                                    try:
                                        import socket
                                        from urllib.parse import urlparse
                                        parsed = urlparse(ws_url)
                                        host = parsed.hostname
                                        port_num = parsed.port
                                        if host and port_num:
                                            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                            sock.settimeout(1)
                                            result = sock.connect_ex((host, port_num))
                                            sock.close()
                                            if result == 0:
                                                logger.info(f"[driver_creation] ✓ 타겟 {pt.get('id')} WebSocket 연결 가능 확인됨 (포트: {self.port})")
                                            else:
                                                logger.warning(f"[driver_creation] 타겟 {pt.get('id')} WebSocket 연결 불가 (포트: {self.port})")
                                    except Exception as e:
                                        logger.debug(f"[driver_creation] WebSocket 확인 중 오류 (무시): {e}")
                    except Exception as e:
                        logger.warning(f"[driver_creation] 타겟 재확인 중 오류 (계속 진행): {e}")
                    
                    logger.info(f"[driver_creation] webdriver.Chrome() 호출 시작 (포트: {self.port})")
                    logger.info(f"[driver_creation] service: {service} (포트: {self.port})")
                    logger.info(f"[driver_creation] options.debuggerAddress: {options.experimental_options.get('debuggerAddress', 'N/A')} (포트: {self.port})")
                    
                    # Android Chrome 원격 디버깅에서는 service를 None으로 시도
                    # (ChromeDriver가 이미 실행 중인 Chrome에 연결하므로 서비스가 필요 없을 수 있음)
                    try:
                        logger.info(f"[driver_creation] service=None으로 WebDriver 생성 시도 (포트: {self.port})")
                        driver_result['driver'] = webdriver.Chrome(options=options)
                        logger.info(f"[driver_creation] ✓ service=None으로 WebDriver 생성 성공 (포트: {self.port})")
                    except Exception as e1:
                        logger.warning(f"[driver_creation] service=None 실패, service 객체로 재시도 중... (포트: {self.port}): {e1}")
                        # service=None이 실패하면 service 객체로 재시도
                        driver_result['driver'] = webdriver.Chrome(service=service, options=options)
                        logger.info(f"[driver_creation] ✓ service 객체로 WebDriver 생성 성공 (포트: {self.port})")
                    
                    logger.info(f"[driver_creation] webdriver.Chrome() 호출 완료 (포트: {self.port})")
                    driver_result['completed'] = True
                except Exception as e:
                    logger.error(f"[driver_creation] webdriver.Chrome() 호출 중 오류 (포트: {self.port}): {e}", exc_info=True)
                    # 오류 상세 정보 로깅
                    logger.error(f"[driver_creation] 오류 타입: {type(e).__name__}")
                    logger.error(f"[driver_creation] 오류 메시지: {str(e)}")
                    driver_result['error'] = e
                    driver_result['completed'] = True
            
            # 드라이버 생성 스레드 시작
            logger.info(f"[_setup_stealth_driver] 드라이버 생성 스레드 생성 중... (포트: {self.port})")
            driver_thread = threading.Thread(target=driver_creation, daemon=False)
            start_time = time.time()
            logger.info(f"[_setup_stealth_driver] 드라이버 생성 스레드 시작 (타임아웃: 10초, 포트: {self.port})")
            driver_thread.start()
            
            # 10초 타임아웃 대기
            logger.info(f"[_setup_stealth_driver] 드라이버 생성 스레드 대기 중... (포트: {self.port})")
            driver_thread.join(timeout=10)
            elapsed_time = time.time() - start_time
            logger.info(f"[_setup_stealth_driver] 드라이버 생성 스레드 대기 완료 ({elapsed_time:.1f}초 경과, 포트: {self.port})")
            
            # 타임아웃 체크
            if driver_thread.is_alive():
                logger.error(f"[_setup_stealth_driver] 드라이버 생성 타임아웃 ({elapsed_time:.1f}초 경과) - 스레드가 여전히 실행 중 (포트: {self.port})")
                # 스레드가 살아있으면 타임아웃 발생
                # Windows에서는 스레드를 강제 종료할 수 없으므로 예외만 발생
                raise TimeoutError(f"드라이버 생성 타임아웃 (포트: {self.port}) - 10초 내 연결 실패")
            
            logger.info(f"[_setup_stealth_driver] 드라이버 생성 스레드 완료 ({elapsed_time:.1f}초 소요, 포트: {self.port})")
            
            # 결과 확인
            logger.info(f"[_setup_stealth_driver] 드라이버 생성 결과 확인 중... (포트: {self.port})")
            if driver_result['error']:
                logger.error(f"[_setup_stealth_driver] 드라이버 생성 중 오류 발생 (포트: {self.port}): {driver_result['error']}", exc_info=True)
                raise driver_result['error']
            
            if driver_result['driver'] is None:
                logger.error(f"[_setup_stealth_driver] 드라이버 생성 실패: 알 수 없는 오류 (포트: {self.port})")
                raise Exception(f"드라이버 생성 실패: 알 수 없는 오류 (포트: {self.port})")
            
            self.driver = driver_result['driver']
            logger.info(f"[_setup_stealth_driver] [3단계] WebDriver 생성 완료 (포트: {self.port})")
                
            logger.info(f"[_setup_stealth_driver] 드라이버 생성 완료 (포트: {self.port})")
        except TimeoutError as e:
            logger.error(f"[포트 {self.port}] 드라이버 생성 타임아웃: {e}")
            raise
        except Exception as e:
            logger.error(f"[포트 {self.port}] 드라이버 생성 실패: {e}")
            raise
        
        # 스텔스 스크립트 주입
        logger.info(f"[_setup_stealth_driver] [4단계] 스텔스 스크립트 주입 시작 (포트: {self.port})")
        try:
            self._apply_stealth_scripts()
            logger.info(f"[_setup_stealth_driver] [4단계] 스텔스 스크립트 주입 완료 (포트: {self.port})")
        except Exception as e:
            logger.error(f"[_setup_stealth_driver] 스텔스 스크립트 주입 실패 (포트: {self.port}): {e}", exc_info=True)
            raise
        
        logger.info(f"[_setup_stealth_driver] ✓ 스텔스 드라이버 초기화 완료 (포트: {self.port})")
    
    def _apply_stealth_scripts(self):
        """강력한 봇 탐지 회피 스크립트"""
        stealth_js = """
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        window.navigator.chrome = {runtime: {}, loadTimes: function() {}, csi: function() {}, app: {}};
        
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        Object.defineProperty(navigator, 'languages', {get: () => ['ko-KR', 'ko', 'en-US', 'en']});
        
        // Canvas Fingerprinting 회피
        const getImageData = CanvasRenderingContext2D.prototype.getImageData;
        CanvasRenderingContext2D.prototype.getImageData = function(...args) {
            const imageData = getImageData.apply(this, args);
            for (let i = 0; i < imageData.data.length; i += 4) {
                imageData.data[i] += Math.floor(Math.random() * 3) - 1;
            }
            return imageData;
        };
        
        // WebGL Fingerprinting 회피
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            if (parameter === 37445) return 'Intel Inc.';
            if (parameter === 37446) return 'Intel Iris OpenGL Engine';
            return getParameter.apply(this, [parameter]);
        };
        
        console.log('✓ Stealth mode activated');
        """
        
        try:
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': stealth_js
            })
        except:
            try:
                self.driver.execute_script(stealth_js)
            except:
                pass
    
    def human_delay(self, min_sec=1, max_sec=3):
        """사람처럼 딜레이"""
        time.sleep(random.uniform(min_sec, max_sec))
    
    def human_scroll(self, distance=None):
        """사람처럼 스크롤"""
        if distance is None:
            distance = random.randint(300, 700)
        self.driver.execute_script(f"window.scrollBy(0, {distance});")
        self.human_delay(0.5, 1.5)
    
    def human_type(self, element, text):
        """사람처럼 타이핑"""
        element.click()
        self.human_delay(0.2, 0.5)
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.05, 0.2))
        self.human_delay(0.3, 0.8)
    
    def navigate_to_naver(self):
        """네이버 접속"""
        logger.info("네이버 접속 중...")
        self.driver.get("https://m.naver.com")
        self.human_delay(2, 4)
    
    def search_keyword(self, keyword):
        """키워드 검색"""
        logger.info(f"키워드 검색: {keyword}")
        try:
            search_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='search'], input.search_input"))
            )
            self.human_type(search_input, keyword)
            
            try:
                search_btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit'], .btn_search")
                search_btn.click()
            except:
                from selenium.webdriver.common.keys import Keys
                search_input.send_keys(Keys.RETURN)
            
            self.human_delay(2, 4)
        except Exception as e:
            logger.error(f"검색 실패: {e}")
    
    def click_by_nvmid(self, nvmid):
        """nvmid로 상품 클릭"""
        logger.info(f"상품 클릭: nvmid={nvmid}")
        
        click_script = create_click_result_script(nvmid)
        result = self.driver.execute_script(click_script)
        
        if result and isinstance(result, dict) and result.get('success'):
            logger.info(f"✓ 상품 클릭 완료: {result.get('nvmid')}")
            self.human_delay(2, 4)
            return True
        else:
            logger.warning(f"상품을 찾지 못했습니다: {result.get('reason') if result else 'unknown'}")
            return False
    
    def random_behavior(self):
        """랜덤 브라우징 행동"""
        behaviors = [
            lambda: self.human_scroll(random.randint(100, 300)),
            lambda: self.human_delay(1, 2),
        ]
        random.choice(behaviors)()
    
    def close(self):
        """드라이버 종료"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass

    def click_purchase_additional_info(self):
        """구매 추가정보 버튼 클릭"""
        try:
            click_info_script = """
            (function() {
                window.scrollTo(0, document.body.scrollHeight);
                var infoBtn = document.querySelector('a[data-shp-area-id="info"]') ||
                            Array.from(document.querySelectorAll('a')).find(a => 
                                a.textContent.includes('구매 추가정보'));
                if (infoBtn) {
                    infoBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    setTimeout(() => infoBtn.click(), 500);
                    return true;
                }
                return false;
            })();
            """
            result = self.driver.execute_script(click_info_script)
            self.human_delay(2, 3)  # 클릭 후 대기
            return result
        except Exception as e:
            logger.warning(f"구매 추가정보 버튼 클릭 실패: {e}")
            return False                


def test_single_iteration_stealth(row_data, iteration_id, port):
    """
    봇 탐지 회피 기능이 추가된 단일 반복 테스트 (순차 실행)
    """
    crawler = None
    adb = None
    
    try:
        # ADB Manager 초기화
        adb = get_adb_manager()
        
        if not adb.check_connection():
            logger.error(f"[반복 {iteration_id}] ADB 연결 실패")
            return False
        
        # IP 변경
        data_manager = DataConnectionManager(adb=adb)
        data_manager.toggle_data_connection(disable_duration=3)
        time.sleep(5)
        
        # 포트 포워딩 (재시도 로직 포함)
        port_forwarding_success = False
        max_retries = 3
        for retry in range(max_retries):
            if setup_port_forwarding(adb, port):
                port_forwarding_success = True
                break
            else:
                if retry < max_retries - 1:
                    logger.warning(f"[반복 {iteration_id}] 포트 포워딩 설정 실패, {retry + 1}/{max_retries} 재시도 중... (포트: {port})")
                    if not adb.check_connection():
                        logger.error(f"[반복 {iteration_id}] ADB 연결이 끊어졌습니다.")
                        return False
                    time.sleep(2)
                else:
                    logger.error(f"[반복 {iteration_id}] 포트 포워딩 설정 실패: 최대 재시도 횟수 초과 (포트: {port})")
        
        if not port_forwarding_success:
            logger.error(f"[반복 {iteration_id}] 포트 포워딩 설정 실패로 인해 크롤링을 중단합니다. (포트: {port})")
            return False
        
        try:
            ensure_chromedriver_138(port)
        except Exception as e:
            logger.error(f"[반복 {iteration_id}] ChromeDriver 준비 실패: {e}")
            return False
        
        # Chrome DevTools 연결 확인 (세션 생성 가능 여부 확인)
        logger.info(f"[반복 {iteration_id}] Chrome DevTools 연결 확인 중... (포트: {port})")
        chrome_socket_ready = False
        max_chrome_check_attempts = 5  # 최대 5번 확인 (약 2.5초)
        
        # Chrome 상태 확인 후 필요시에만 시작
        logger.info(f"[반복 {iteration_id}] Chrome 상태 확인 중...")
        chrome_running = False
        try:
            # Chrome 프로세스 확인
            result = adb.run_command('shell', 'ps', '-A', timeout=3)
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if 'com.android.chrome' in line:
                        chrome_running = True
                        break
        except:
            pass
        
        if chrome_running:
            logger.info(f"[반복 {iteration_id}] Chrome이 이미 실행 중입니다. 재시작합니다...")
            if not restart_chrome():
                logger.error(f"[반복 {iteration_id}] Chrome 재시작 실패")
                return False
        else:
            logger.info(f"[반복 {iteration_id}] Chrome이 종료된 상태입니다. 시작합니다...")
            if not open_chrome():
                logger.error(f"[반복 {iteration_id}] Chrome 시작 실패")
                return False
        
        # Chrome 시작 후 DevTools가 준비될 때까지 충분히 대기
        logger.info(f"[반복 {iteration_id}] Chrome DevTools 준비 대기 중... (최대 10초)")
        time.sleep(5)  # Chrome이 완전히 시작될 때까지 대기

        # 835-884줄 수정 (소켓 확인을 세션 확인 함수로 대체)
        for check_attempt in range(max_chrome_check_attempts):
            try:
                # 세션 상태 확인 (소켓 직접 사용 대신)
                from session_middleware import check_android_chrome_session
                session_status = check_android_chrome_session(port)
                
                if session_status['port_forwarding'] and session_status['devtools_ready']:
                    chrome_socket_ready = True
                    logger.info(f"[반복 {iteration_id}] ✓ Chrome DevTools 연결 확인됨 (포트: {port})")
                    logger.info(f"[반복 {iteration_id}]   - 발견된 타겟 수: {session_status['targets_count']}개")
                    break
                else:
                    logger.debug(f"[반복 {iteration_id}] Chrome 세션 상태 - "
                               f"Chrome 실행: {session_status['chrome_running']}, "
                               f"포트 포워딩: {session_status['port_forwarding']}, "
                               f"DevTools 준비: {session_status['devtools_ready']}")
                
                if check_attempt < max_chrome_check_attempts - 1:
                    logger.debug(f"[반복 {iteration_id}] Chrome 연결 대기 중... ({check_attempt + 1}/{max_chrome_check_attempts})")
                    time.sleep(0.5)
            except Exception as e:
                logger.debug(f"[반복 {iteration_id}] 세션 확인 중 오류 (포트: {port}): {e}")
                time.sleep(0.5)
        
        # Chrome 연결 확인 실패 시 상세 정보 로깅 및 세션 정리
        if not chrome_socket_ready:
            logger.error(f"[반복 {iteration_id}] ✗ Chrome DevTools 연결 실패 (포트: {port})")
            
            # 세션 상태 재확인
            try:
                from session_middleware import check_android_chrome_session
                session_status = check_android_chrome_session(port)
                
                if session_status['port_forwarding']:
                    logger.error(f"[반복 {iteration_id}]   - 포트 {port}는 열려있지만 Chrome DevTools API에 접근할 수 없습니다.")
                    logger.error(f"[반복 {iteration_id}]   - Chrome 실행: {session_status['chrome_running']}, "
                               f"DevTools 준비: {session_status['devtools_ready']}, "
                               f"타겟 수: {session_status['targets_count']}")
                    
                    # 세션 정리 시도
                    logger.info(f"[반복 {iteration_id}] 세션 정리 시도 중...")
                    from session_middleware import clear_android_chrome_session
                    clear_android_chrome_session(port, adb)
                else:
                    logger.error(f"[반복 {iteration_id}]   - 포트 {port}가 열려있지 않습니다.")
            except Exception as e:
                logger.error(f"[반복 {iteration_id}]   - 세션 상태 확인 실패: {e}")
            
            return False
        
        # 스텔스 크롤러 생성 (ChromeDriver는 이미 다운로드됨)
        logger.info(f"[반복 {iteration_id}] ========================================")
        logger.info(f"[반복 {iteration_id}] 스텔스 크롤러 생성 시작 (포트: {port})")
        logger.info(f"[반복 {iteration_id}] ========================================")
        try:
            crawler = StealthNaverCrawler(port=port)
            logger.info(f"[반복 {iteration_id}] ✓ 스텔스 크롤러 생성 완료 (포트: {port})")
        except Exception as e:
            logger.error(f"[반복 {iteration_id}] ✗ 스텔스 크롤러 생성 실패 (포트: {port}): {e}", exc_info=True)
            raise
        
        # 네이버 접속
        crawler.navigate_to_naver()
        
        # 랜덤 행동
        crawler.random_behavior()
        
        # 메인 키워드 검색
        crawler.search_keyword(row_data['main_keyword'])
        
        # 랜덤 행동
        crawler.random_behavior()
        
        # 새 검색어로 검색
        crawler.search_keyword(row_data['base_search_keyword'])
        
        # 랜덤 행동
        crawler.random_behavior()
        
        # nvmid로 상품 클릭
        crawler.click_by_nvmid(str(row_data['nv_mid']))
        
        # 구매 추가정보 버튼 클릭
        crawler.click_purchase_additional_info()
        
        # 페이지에서 랜덤 행동
        for _ in range(2):
            crawler.random_behavior()
        
        logger.info(f"[반복 {iteration_id}] 스텔스 크롤링 완료")
        return True
        
    except Exception as e:
        logger.error(f"[반복 {iteration_id}] 오류: {e}", exc_info=True)
        return False
    finally:
        if crawler:
            crawler.close()
        # 휴대폰의 Chrome 앱 종료 (백그라운드 실행 방지)
        try:
            logger.info(f"[반복 {iteration_id}] Chrome 앱 종료 중...")
            close_chrome()
            logger.info(f"[반복 {iteration_id}] Chrome 앱 종료 완료")
        except Exception as e:
            logger.warning(f"[반복 {iteration_id}] Chrome 종료 중 오류: {e}")

        time.sleep(2)


def cleanup_ports_and_processes():
    """
    모든 반복 완료 후 할당된 포트와 프로세스 정리
    - ADB 포트 포워딩 제거
    - 포트를 사용하는 프로세스 확인 및 제거 (ADB 제외)
    """
    logger.info("=" * 50)
    logger.info("포트 및 프로세스 정리 시작")
    logger.info("=" * 50)
    
    try:
        # ADB Manager 가져오기
        adb = get_adb_manager()
        
        if not adb.check_connection():
            logger.warning("ADB 연결이 없어 포트 포워딩만 제거합니다.")
        
        # 포트 정리
        port = PORT
        logger.info(f"\n[포트 정리] 포트 {port} 정리 중...")
        
        # 1. ADB 포트 포워딩 제거
        try:
            logger.info(f"[포트 정리] 포트 {port}의 ADB 포워딩 제거 시도...")
            result = adb.run_command('forward', '--remove', f'tcp:{port}', timeout=3)
            if result.returncode == 0:
                logger.info(f"✓ [포트 정리] 포트 {port}의 ADB 포워딩 제거 완료")
            else:
                error_msg = result.stderr if hasattr(result, 'stderr') and result.stderr else str(result)
                logger.debug(f"[포트 정리] 포트 {port}의 ADB 포워딩 제거 실패: {error_msg}")
        except Exception as e:
            logger.warning(f"[포트 정리] 포트 {port}의 ADB 포워딩 제거 중 오류: {e}")
        
        # 2. 포트 사용 여부 확인 (세션 확인 함수 사용)
        time.sleep(0.5)  # 포워딩 제거 후 대기
        try:
            from session_middleware import check_android_chrome_session
            session_status = check_android_chrome_session(port)
            port_in_use = session_status['port_forwarding']
        except Exception as e:
            logger.warning(f"[포트 정리] 세션 확인 중 오류: {e}")
            port_in_use = False  # 확인 실패 시 False로 간주
        
        if port_in_use:
            logger.info(f"[포트 정리] 포트 {port}가 여전히 사용 중입니다. 프로세스 확인 중...")
            
            # 프로세스 정보 확인 (test5.py의 함수 사용)
            try:
                from test5 import get_port_process_info
                process_info = get_port_process_info(port)
                
                if process_info:
                    process_name = process_info['name'].lower()
                    pid = process_info['pid']
                    
                    # ADB 프로세스는 정상이므로 제거하지 않음
                    if 'adb' in process_name:
                        logger.info(f"[포트 정리] 포트 {port}는 ADB 프로세스가 사용 중입니다. (정상, 제거하지 않음)")
                    else:
                        logger.warning(f"[포트 정리] 포트 {port}를 사용하는 프로세스 발견:")
                        logger.warning(f"  - PID: {pid}")
                        logger.warning(f"  - 프로세스 이름: {process_info['name']}")
                        logger.warning(f"  - 명령줄: {process_info['command']}")
                        
                        # PortManager를 사용하여 프로세스 종료 (선택적)
                        try:
                            from port_manager import PortManager
                            port_manager = PortManager()
                            logger.info(f"[포트 정리] 포트 {port}의 프로세스 종료 시도...")
                            success = port_manager.free_port(port, force=True, wait_time=2)
                            if success:
                                logger.info(f"✓ [포트 정리] 포트 {port}의 프로세스 종료 완료")
                            else:
                                logger.warning(f"[포트 정리] 포트 {port}의 프로세스 종료 실패")
                        except Exception as e:
                            logger.warning(f"[포트 정리] 포트 {port}의 프로세스 종료 중 오류: {e}")
                else:
                    logger.warning(f"[포트 정리] 포트 {port}를 사용하는 프로세스 정보를 가져올 수 없습니다.")
            except Exception as e:
                logger.warning(f"[포트 정리] 포트 {port}의 프로세스 정보 확인 중 오류: {e}")
        else:
            logger.info(f"✓ [포트 정리] 포트 {port}는 사용 중이 아닙니다.")
        
        logger.info("\n" + "=" * 50)
        logger.info("포트 및 프로세스 정리 완료")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"포트 및 프로세스 정리 중 오류: {e}", exc_info=True)


def main():
    """메인 함수 (순차 실행)"""
    logger.info("=" * 50)
    logger.info("스텔스 네이버 크롤러 시작 (순차 실행 모드)")
    logger.info("=" * 50)
    
    try:
        try:
            # 여러 인코딩 시도 (한국어 CSV 파일은 보통 cp949나 euc-kr 사용)
            encodings = ['cp949', 'euc-kr', 'utf-8', 'latin-1']
            df = None
            
            for encoding in encodings:
                try:
                    df = pd.read_csv('keyword_data.csv', encoding=encoding)
                    logger.info(f"CSV 로드 성공 (인코딩: {encoding}): {len(df)}개 행")
                    break
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    logger.warning(f"인코딩 {encoding} 시도 중 오류: {e}")
                    continue
            
            if df is None:
                logger.error("CSV 파일을 읽을 수 없습니다. 지원되는 인코딩을 찾을 수 없습니다.")
                return
        except Exception as e:
            logger.error(f"CSV 읽기 실패: {e}")
            return
        
        try:
            # 순차 실행: 각 행을 하나씩 처리
            for idx, row in df.iterrows():
                iteration_id = idx + 1
                port = PORT
                
                logger.info("=" * 50)
                logger.info(f"[반복 {iteration_id}] 크롤링 시작 (포트: {port})")
                logger.info("=" * 50)
                
                success = test_single_iteration_stealth(row, iteration_id, port)
                if success:
                    logger.info(f"[반복 {iteration_id}] ✓ 성공")
                else:
                    logger.warning(f"[반복 {iteration_id}] ✗ 실패")
                
                # 다음 반복 전 대기
                if idx < len(df) - 1:  # 마지막 반복이 아니면
                    logger.info(f"[반복 {iteration_id}] 다음 반복 전 2초 대기...")
                    time.sleep(2)
            
            logger.info("=" * 50)
            logger.info("모든 크롤링 완료")
            logger.info("=" * 50)
            
        except Exception as e:
            logger.error(f"크롤링 중 오류: {e}", exc_info=True)
    finally:
        # 모든 반복 완료 후 포트 및 프로세스 정리
        cleanup_ports_and_processes()


if __name__ == '__main__':
    main()
