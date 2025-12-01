"""
매일 스케줄링된 작업 실행 (APScheduler 사용)
- 매일 6시: test_ip_connect.py 실행하여 프록시 테스트 및 필터링
- 매일 6시 30분: proxy_chain.py 시작 후 collect_naver_cookies.py 실행
"""

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import time
import subprocess
import sys
import os
import logging
from datetime import datetime
import threading
import asyncio
import importlib.util
import importlib
import argparse

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scheduler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 에러 로깅 설정
error_logger = logging.getLogger('error')
error_handler = logging.FileHandler('error.log', encoding='utf-8')
error_handler.setLevel(logging.ERROR)
error_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
error_handler.setFormatter(error_formatter)
error_logger.addHandler(error_handler)

# proxy_chain.py 프로세스 저장
proxy_chain_process = None
proxy_chain_thread = None


def log_error(message, exc_info=False):
    """오류를 error.log에 기록"""
    error_logger.error(message, exc_info=exc_info)


async def test_proxies_and_get_success_list():
    """test_ip_connect.py를 실행하여 성공한 프록시 리스트 가져오기"""
    try:
        # test_ip_connect.py 모듈 import # 추후 dbml.sql 에 proxy_status 테이블의 ip 로 바꾸기.
        test_ip_connect_path = os.path.join("proxy_config", "test_ip_connect.py")
        if not os.path.exists(test_ip_connect_path):
            test_ip_connect_path = "test_ip_connect.py"
        
        spec = importlib.util.spec_from_file_location("test_ip_connect", test_ip_connect_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"test_ip_connect.py를 로드할 수 없습니다: {test_ip_connect_path}")
        
        test_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(test_module)
        
        # test_all_proxies 함수 실행
        success_proxies = await test_module.test_all_proxies()
        return success_proxies
        
    except Exception as e:
        log_error(f"프록시 테스트 중 오류: {e}", exc_info=True)
        return []


def save_success_proxies_to_file(success_proxies):
    """
    성공한 프록시를 JSON 파일로 저장
    proxy_chain.py가 시작될 때 이 파일을 읽어서 WHITELIST_PROXIES로 사용
    """
    try:
        import json
        whitelist_file = os.path.join("proxy_config", "whitelist_proxies.json")
        
        with open(whitelist_file, 'w', encoding='utf-8') as f:
            json.dump(success_proxies, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✓ 성공한 프록시 저장 완료: {whitelist_file} ({len(success_proxies)}개)")
        for i, proxy in enumerate(success_proxies, 1):
            logger.info(f"  {i}. {proxy['host']}:{proxy['port']}")
        
        return True
        
    except Exception as e:
        log_error(f"성공한 프록시 파일 저장 실패: {e}", exc_info=True)
        return False


def load_whitelist_proxies_from_file():
    """
    whitelist_proxies.json 파일에서 프록시 목록 로드
    proxy_chain.py를 실행하기 전에 호출하여 WHITELIST_PROXIES 업데이트
    """
    try:
        import json
        whitelist_file = os.path.join("proxy_config", "whitelist_proxies.json")
        
        if not os.path.exists(whitelist_file):
            logger.warning(f"whitelist_proxies.json 파일이 없습니다: {whitelist_file}")
            return None
        
        with open(whitelist_file, 'r', encoding='utf-8') as f:
            proxies = json.load(f)
        
        logger.info(f"✓ whitelist_proxies.json에서 {len(proxies)}개 프록시 로드")
        return proxies
        
    except Exception as e:
        log_error(f"whitelist_proxies.json 파일 로드 실패: {e}", exc_info=True)
        return None


def update_proxy_chain_module(success_proxies):
    """
    proxy_chain.py 모듈의 WHITELIST_PROXIES를 런타임에 업데이트
    proxy_chain.py 파일을 직접 수정하지 않고 모듈 변수만 변경
    """
    try:
        # proxy_chain 모듈 import
        proxy_chain_path = os.path.join("proxy_config", "proxy_chain.py")
        if not os.path.exists(proxy_chain_path):
            proxy_chain_path = "proxy_chain.py"
        
        spec = importlib.util.spec_from_file_location("proxy_chain", proxy_chain_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"proxy_chain.py를 로드할 수 없습니다: {proxy_chain_path}")
        
        # 모듈이 이미 로드되어 있으면 다시 로드
        if 'proxy_config.proxy_chain' in sys.modules:
            importlib.reload(sys.modules['proxy_config.proxy_chain'])
            proxy_chain_module = sys.modules['proxy_config.proxy_chain']
        else:
            proxy_chain_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(proxy_chain_module)
        
        # WHITELIST_PROXIES 업데이트
        proxy_chain_module.WHITELIST_PROXIES = success_proxies
        
        logger.info(f"✓ proxy_chain 모듈의 WHITELIST_PROXIES 업데이트 완료: {len(success_proxies)}개")
        
        return proxy_chain_module
        
    except Exception as e:
        log_error(f"proxy_chain 모듈 업데이트 실패: {e}", exc_info=True)
        return None

def select_top_n_proxies(success_proxies, n=6):
    """
    성공한 프록시 중 상위 N개만 선택
    
    Args:
        success_proxies: 성공한 프록시 리스트
        n: 선택할 프록시 개수 (기본값: 6)
    
    Returns:
        list: 선택된 프록시 리스트
    """
    if not success_proxies:
        return []
    
    # 상위 N개만 선택 (연결 성공 순서대로)
    selected = success_proxies[:n]
    logger.info(f"✓ 상위 {len(selected)}개 프록시 선택: {len(success_proxies)}개 중")
    return selected

def run_test_ip_connect():
    """매일 6시에 test_ip_connect.py 실행 및 프록시 필터링"""
    logger.info("=" * 60)
    logger.info("test_ip_connect.py 실행 시작")
    logger.info("=" * 60)
    
    try:
        # 비동기 함수 실행
        success_proxies = asyncio.run(test_proxies_and_get_success_list())
        
        if not success_proxies:
            logger.warning("성공한 프록시가 없습니다")
            log_error("프록시 테스트 결과: 성공한 프록시가 없습니다")
            return        
        logger.info(f"✓ {len(success_proxies)}개의 프록시 연결 성공")
        # ⭐ 상위 6개만 선택 (임시)
        # 성공한 프록시를 파일로 저장 (proxy_chain.py가 시작 시 읽음) -> 잠시 선택된 6개 프록시를 저장하기 위해 임시로 사용
        # selected_proxies = select_top_n_proxies(success_proxies, n=6)        
        # if save_success_proxies_to_file(selected_proxies):
        #     logger.info("✓ 성공한 프록시 목록 저장 완료 (proxy_chain.py에서 사용)")
        # 성공한 프록시를 파일로 저장 (proxy_chain.py가 시작 시 읽음) -> 잠시 선택된 6개 프록시를 저장하기 위해 임시로 사용
        if save_success_proxies_to_file(success_proxies):
            logger.info("✓ 성공한 프록시 목록 저장 완료 (proxy_chain.py에서 사용)")
        else:
            log_error("성공한 프록시 목록 저장 실패")
            
    except Exception as e:
        log_error(f"test_ip_connect.py 실행 중 오류: {e}", exc_info=True)
        logger.error(f"test_ip_connect.py 실행 실패: {e}", exc_info=True)


def run_proxy_chain_in_thread():
    """proxy_chain.py를 별도 스레드에서 실행"""
    global proxy_chain_thread
    
    try:
        # proxy_chain 모듈 import 및 실행
        proxy_chain_path = os.path.join("proxy_config", "proxy_chain.py")
        if not os.path.exists(proxy_chain_path):
            proxy_chain_path = "proxy_chain.py"
        
        spec = importlib.util.spec_from_file_location("proxy_chain", proxy_chain_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"proxy_chain.py를 로드할 수 없습니다: {proxy_chain_path}")
        
        proxy_chain_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(proxy_chain_module)
        
        # 성공한 프록시 목록 로드 및 업데이트
        success_proxies = load_whitelist_proxies_from_file()
        if success_proxies:
            proxy_chain_module.WHITELIST_PROXIES = success_proxies
            logger.info(f"✓ WHITELIST_PROXIES 업데이트: {len(success_proxies)}개 프록시")
        else:
            logger.warning("성공한 프록시 목록을 로드할 수 없습니다. 기본 WHITELIST_PROXIES 사용")
        
        # 별도 스레드에서 proxy_chain 실행
        def run_proxy_chain_async():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                proxy_chain_module.main() 
                # 스레드에서 proxy_chain_module.main()을 호출할 때, 새 스레드에는 asyncio 이벤트 루프가 없습니다. -> 새 스레드에서 asyncio 이벤트 루프를 생성하고 설정해야 함.
            except Exception as e:
                log_error(f"proxy_chain.py 실행 중 오류: {e}", exc_info=True)
        
        proxy_chain_thread = threading.Thread(target=run_proxy_chain_async, daemon=True)
        proxy_chain_thread.start()
        
        logger.info("✓ proxy_chain.py 스레드 시작")
        
        # 프록시 서버가 시작될 때까지 대기 (최대 10초)
        import socket
        for i in range(10):
            time.sleep(1)
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(('127.0.0.1', 1080))
                sock.close()
                if result == 0:
                    logger.info("✓ proxy_chain.py 서버 시작 확인 (포트 1080)")
                    return True
            except:
                pass
        
        logger.warning("⚠ proxy_chain.py 서버 시작 확인 실패 (계속 진행)")
        return True
        
    except Exception as e:
        log_error(f"proxy_chain.py 시작 실패: {e}", exc_info=True)
        logger.error(f"proxy_chain.py 시작 실패: {e}", exc_info=True)
        return False


def run_proxy_chain():
    """proxy_chain.py를 백그라운드에서 실행 (성공한 프록시 목록 사용)"""
    return run_proxy_chain_in_thread()


def run_collect_naver_cookies():
    """collect_naver_cookies.py 실행"""
    logger.info("=" * 60)
    logger.info("collect_naver_cookies.py 실행 시작")
    logger.info("=" * 60)
    
    try:
        script_path = "collect_naver_cookies.py"
        if not os.path.exists(script_path):
            logger.error("collect_naver_cookies.py 파일을 찾을 수 없습니다")
            log_error("collect_naver_cookies.py 파일을 찾을 수 없습니다")
            return
        
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=1800  # 30분 타임아웃
        )
        
        logger.info(f"collect_naver_cookies.py 실행 완료 (반환 코드: {result.returncode})")
        if result.stdout:
            logger.info(f"출력:\n{result.stdout}")
        if result.stderr:
            logger.warning(f"오류:\n{result.stderr}")
            if result.returncode != 0:
                log_error(f"collect_naver_cookies.py 실행 오류:\n{result.stderr}")
            
    except subprocess.TimeoutExpired:
        error_msg = "collect_naver_cookies.py 실행 타임아웃"
        log_error(error_msg)
        logger.error(error_msg)
    except Exception as e:
        log_error(f"collect_naver_cookies.py 실행 실패: {e}", exc_info=True)
        logger.error(f"collect_naver_cookies.py 실행 실패: {e}", exc_info=True)


def run_collect_naver_cookies_all():
    """collect_naver_cookies.py 실행 (모든 프록시에 대해)"""
    logger.info("=" * 60)
    logger.info("collect_naver_cookies.py 실행 시작 (모든 프록시)")
    logger.info("=" * 60)
    
    try:
        script_path = "collect_naver_cookies.py"
        if not os.path.exists(script_path):
            logger.error("collect_naver_cookies.py 파일을 찾을 수 없습니다")
            log_error("collect_naver_cookies.py 파일을 찾을 수 없습니다")
            return
        
        # ⭐ --all 인자 추가하여 모든 프록시에 대해 수집
        result = subprocess.run(
            [sys.executable, script_path, "--all"],  # --all 인자 추가
            capture_output=True,
            text=True,
            timeout=7200  # 2시간 타임아웃 (프록시가 많을 수 있으므로)
        )
        
        logger.info(f"collect_naver_cookies.py 실행 완료 (반환 코드: {result.returncode})")
        if result.stdout:
            logger.info(f"출력:\n{result.stdout}")
        if result.stderr:
            logger.warning(f"오류:\n{result.stderr}")
            if result.returncode != 0:
                log_error(f"collect_naver_cookies.py 실행 오류:\n{result.stderr}")
            
    except subprocess.TimeoutExpired:
        error_msg = "collect_naver_cookies.py 실행 타임아웃"
        log_error(error_msg)
        logger.error(error_msg)
    except Exception as e:
        log_error(f"collect_naver_cookies.py 실행 실패: {e}", exc_info=True)
        logger.error(f"collect_naver_cookies.py 실행 실패: {e}", exc_info=True)


def run_test_web_selenium():
    """test_web_selenium.py 실행"""
    logger.info("=" * 60)
    logger.info("test_web_selenium.py 실행 시작")
    logger.info("=" * 60)
    
    try:
        script_path = "test_web_selenium.py"
        if not os.path.exists(script_path):
            logger.error("test_web_selenium.py 파일을 찾을 수 없습니다")
            log_error("test_web_selenium.py 파일을 찾을 수 없습니다")
            return None
        
        logger.info(f"test_web_selenium.py 프로세스 시작...")
        process = subprocess.Popen(
            [sys.executable, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        logger.info(f"test_web_selenium.py 프로세스 시작됨 (PID: {process.pid})")
        return process
        
    except Exception as e:
        log_error(f"test_web_selenium.py 시작 실패: {e}", exc_info=True)
        logger.error(f"test_web_selenium.py 시작 실패: {e}", exc_info=True)
        return None


def wait_for_test_web_selenium_completion(process, max_wait_seconds=3600):
    """
    test_web_selenium.py 프로세스가 종료될 때까지 대기
    
    Args:
        process: subprocess.Popen 객체
        max_wait_seconds: 최대 대기 시간 (기본값: 1시간)
    
    Returns:
        bool: 정상 종료 여부
    """
    if not process:
        return False
    
    try:
        logger.info(f"test_web_selenium.py 프로세스 종료 대기 중... (최대 {max_wait_seconds}초)")
        
        # 프로세스 종료 대기
        try:
            process.wait(timeout=max_wait_seconds)
            return_code = process.returncode
            logger.info(f"test_web_selenium.py 프로세스 종료됨 (반환 코드: {return_code})")
            
            # 출력 확인
            if process.stdout:
                stdout = process.stdout.read()
                if stdout:
                    logger.info(f"test_web_selenium.py 출력:\n{stdout[:1000]}")  # 처음 1000자만
            
            if process.stderr:
                stderr = process.stderr.read()
                if stderr:
                    logger.warning(f"test_web_selenium.py 오류:\n{stderr[:1000]}")
                    if return_code != 0:
                        log_error(f"test_web_selenium.py 실행 오류:\n{stderr}")
            
            return return_code == 0
            
        except subprocess.TimeoutExpired:
            logger.warning(f"test_web_selenium.py 프로세스가 {max_wait_seconds}초 내에 종료되지 않음")
            log_error(f"test_web_selenium.py 프로세스 타임아웃 ({max_wait_seconds}초)")
            process.kill()
            return False
            
    except Exception as e:
        log_error(f"test_web_selenium.py 프로세스 대기 중 오류: {e}", exc_info=True)
        return False


def is_test_web_selenium_running():
    """test_web_selenium.py 프로세스가 실행 중인지 확인"""
    try:
        import platform
        if platform.system() == 'Windows':
            result = subprocess.run(
                ['wmic', 'process', 'where', 'name="python.exe"', 'get', 'processid,commandline', '/format:list'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return 'test_web_selenium.py' in result.stdout
        else:
            result = subprocess.run(
                ['ps', 'aux'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return 'test_web_selenium.py' in result.stdout
        return False
    except Exception as e:
        logger.debug(f"프로세스 확인 중 오류: {e}")
        return False

def run_collect_cookies_with_proxy(keep_proxy_alive=False):
    """proxy_chain.py 시작 후 collect_naver_cookies.py 실행"""
    global proxy_chain_process, proxy_chain_thread
    
    logger.info("=" * 60)
    logger.info("프록시 체인 시작 및 쿠키 수집 작업 시작")
    logger.info("=" * 60)
    
    # 1. proxy_chain.py 시작
    if not run_proxy_chain():
        error_msg = "proxy_chain.py 시작 실패, 쿠키 수집 작업 중단"
        log_error(error_msg)
        logger.error(error_msg)
        return
    
    # 2. 프록시 서버 시작 대기
    time.sleep(5)
    
    # 3. collect_naver_cookies.py 실행
    run_collect_naver_cookies()
    
    # 4. proxy_chain.py 종료 (keep_proxy_alive=True이면 종료하지 않음)
    if not keep_proxy_alive:
        if proxy_chain_process:
            logger.info("proxy_chain.py 종료 중...")
            proxy_chain_process.terminate()
            try:
                proxy_chain_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proxy_chain_process.kill()
            logger.info("proxy_chain.py 종료 완료")
    else:
        logger.info("✓ proxy_chain.py 유지 (다음 작업을 위해 계속 실행)")


def run_collect_cookies_with_proxy_all(keep_proxy_alive=False):
    """proxy_chain.py 시작 후 collect_naver_cookies.py 실행 (모든 프록시에 대해)"""
    global proxy_chain_process, proxy_chain_thread
    
    logger.info("=" * 60)
    logger.info("프록시 체인 시작 및 쿠키 수집 작업 시작 (모든 프록시)")
    logger.info("=" * 60)
    
    # 1. proxy_chain.py 시작
    if not run_proxy_chain():
        error_msg = "proxy_chain.py 시작 실패, 쿠키 수집 작업 중단"
        log_error(error_msg)
        logger.error(error_msg)
        return
    
    # 2. 프록시 서버 시작 대기
    time.sleep(5)
    
    # 3. collect_naver_cookies.py 실행 (모든 프록시에 대해)
    run_collect_naver_cookies_all()
    
    # 4. proxy_chain.py 종료 (keep_proxy_alive=True이면 종료하지 않음)
    if not keep_proxy_alive:
        if proxy_chain_process:
            logger.info("proxy_chain.py 종료 중...")
            proxy_chain_process.terminate()
            try:
                proxy_chain_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proxy_chain_process.kill()
            logger.info("proxy_chain.py 종료 완료")
    else:
        logger.info("✓ proxy_chain.py 유지 (다음 작업을 위해 계속 실행)")


def run_test_web_selenium_with_proxy():
    """proxy_chain.py 시작 후 test_web_selenium.py 실행 및 종료 대기"""
    global proxy_chain_process, proxy_chain_thread
    
    logger.info("=" * 60)
    logger.info("프록시 체인 시작 및 test_web_selenium.py 실행")
    logger.info("=" * 60)
    
    # 1. proxy_chain.py가 이미 실행 중인지 확인
    import socket
    proxy_already_running = False
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', 1080))
        sock.close()
        if result == 0:
            proxy_already_running = True
            logger.info("✓ proxy_chain.py가 이미 실행 중입니다 (재시작하지 않음)")
    except:
        pass
    
    # 2. proxy_chain.py가 실행 중이 아니면 시작
    if not proxy_already_running:
        if not run_proxy_chain():
            error_msg = "proxy_chain.py 시작 실패, test_web_selenium.py 실행 중단"
            log_error(error_msg)
            logger.error(error_msg)
            return
        
        # 프록시 서버 시작 대기
        time.sleep(5)
    
    # 3. test_web_selenium.py 실행
    selenium_process = run_test_web_selenium()
    
    if not selenium_process:
        error_msg = "test_web_selenium.py 시작 실패"
        log_error(error_msg)
        logger.error(error_msg)
        # proxy_chain.py 종료 (이 함수에서 시작한 경우에만)
        if not proxy_already_running:
            terminate_proxy_chain()
        return
    
    # 4. test_web_selenium.py 프로세스 종료 대기
    logger.info("test_web_selenium.py 프로세스 종료 대기 중...")
    success = wait_for_test_web_selenium_completion(selenium_process, max_wait_seconds=3600)
    
    if success:
        logger.info("✓ test_web_selenium.py 정상 종료")
    else:
        logger.warning("⚠ test_web_selenium.py 비정상 종료 또는 타임아웃")
    
    # 5. test_web_selenium.py 종료 후 proxy_chain.py 종료
    logger.info("test_web_selenium.py 종료 확인, proxy_chain.py 종료 중...")
    terminate_proxy_chain()
    logger.info("✓ proxy_chain.py 종료 완료")


def terminate_proxy_chain():
    """proxy_chain.py 프로세스/스레드 종료"""
    global proxy_chain_process, proxy_chain_thread
    
    try:
        # 스레드 종료 시도
        if proxy_chain_thread and proxy_chain_thread.is_alive():
            logger.info("proxy_chain.py 스레드 종료 중...")
            # 스레드는 daemon이므로 메인 프로세스 종료 시 자동 종료됨
            # 하지만 명시적으로 종료하려면 proxy_chain 모듈의 shutdown_flag 설정 필요
        
        # 프로세스 종료 시도
        if proxy_chain_process:
            logger.info("proxy_chain.py 프로세스 종료 중...")
            proxy_chain_process.terminate()
            try:
                proxy_chain_process.wait(timeout=5)
                logger.info("✓ proxy_chain.py 프로세스 종료 완료")
            except subprocess.TimeoutExpired:
                proxy_chain_process.kill()
                logger.warning("⚠ proxy_chain.py 프로세스 강제 종료")
        
        # 포트 1080을 사용하는 프로세스 확인 및 종료
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', 1080))
            sock.close()
            if result == 0:
                logger.warning("⚠ 포트 1080이 여전히 사용 중입니다")
        except:
            pass
            
    except Exception as e:
        log_error(f"proxy_chain.py 종료 중 오류: {e}", exc_info=True)
        logger.error(f"proxy_chain.py 종료 중 오류: {e}")

def main():
    """스케줄러 메인 함수 (APScheduler 사용)"""
    logger.info("=" * 60)
    logger.info("PyScheduler (APScheduler) 시작")
    logger.info("=" * 60)
    
    # APScheduler 생성
    scheduler = BlockingScheduler()
    
    # 스케줄 등록
    # 매일 6시에 test_ip_connect.py 실행
    scheduler.add_job(
        run_test_ip_connect,
        trigger=CronTrigger(hour=6, minute=0),
        id='test_ip_connect',
        name='프록시 연결 테스트',
        replace_existing=True
    )
    
    # 매일 6시 30분에 proxy_chain.py 시작 후 collect_naver_cookies.py 실행 (모든 프록시에 대해)
    scheduler.add_job(
        run_collect_cookies_with_proxy_all,
        trigger=CronTrigger(hour=6, minute=30),
        id='collect_cookies',
        name='쿠키 수집 (모든 프록시)',
        replace_existing=True
    )
    
    logger.info("등록된 스케줄:")
    logger.info("  - 매일 06:00: test_ip_connect.py 실행 → 성공한 프록시만 WHITELIST_PROXIES에 추가")
    logger.info("  - 매일 06:30: proxy_chain.py 시작 → collect_naver_cookies.py 실행 (모든 프록시에 대해)")
    logger.info("=" * 60)
    
    try:
        # 스케줄러 실행
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("스케줄러 종료 중...")
        scheduler.shutdown()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='스케줄러 실행')
    parser.add_argument('--test-now', action='store_true', help='프록시 테스트를 즉시 실행')
    parser.add_argument('--collect-now', action='store_true', help='쿠키 수집을 즉시 실행 (첫 번째 프록시만)')
    parser.add_argument('--collect-all-now', action='store_true', help='모든 프록시에 대해 쿠키 수집을 즉시 실행')
    parser.add_argument('--all-now', action='store_true', help='모든 작업을 즉시 실행 (테스트 → 쿠키 수집)')
    
    args = parser.parse_args()
    
    try:
        # 즉시 실행 옵션
        if args.test_now:
            logger.info("=" * 60)
            logger.info("즉시 실행: 프록시 테스트")
            logger.info("=" * 60)
            run_test_ip_connect()
            logger.info("프록시 테스트 완료")
        elif args.collect_now:
            logger.info("=" * 60)
            logger.info("즉시 실행: 쿠키 수집 (첫 번째 프록시만)")
            logger.info("=" * 60)
            run_collect_cookies_with_proxy()
            logger.info("쿠키 수집 완료")
        elif args.collect_all_now:
            logger.info("=" * 60)
            logger.info("즉시 실행: 모든 프록시에 대해 쿠키 수집")
            logger.info("=" * 60)
            run_collect_cookies_with_proxy_all()
            logger.info("모든 프록시 쿠키 수집 완료")
        elif args.all_now:
            logger.info("=" * 60)
            # logger.info("즉시 실행: 모든 작업 (테스트 → 쿠키 수집 → test_web_selenium)")
            # logger.info("=" * 60)
            # # 1. 프록시 테스트
            # run_test_ip_connect()
            # time.sleep(5)  # 5초 대기
            # # 2. 쿠키 수집 (프록시 유지)
            # run_collect_cookies_with_proxy(keep_proxy_alive=True)
            # time.sleep(5)  # 5초 대기
            # 3. test_web_selenium.py 실행 (프록시는 이미 실행 중)
            run_test_web_selenium_with_proxy()
            logger.info("모든 작업 완료")
        else:
            # 정상 스케줄러 실행
            main()
    except KeyboardInterrupt:
        logger.info("스케줄러 종료")
        # proxy_chain.py 프로세스 종료
        if proxy_chain_process:
            proxy_chain_process.terminate()
        sys.exit(0)
    except Exception as e:
        log_error(f"스케줄러 실행 중 치명적 오류: {e}", exc_info=True)
        sys.exit(1)

# select_top_n_proxies 로 ip connect 를 바꿧으니 현재는 300개 ip list.txt 를 넣어도 무조건 상위 6개만 넣어짐.
