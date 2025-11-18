"""
테스트용 크롤러
주의사항 1,2,3 무시:
- 병렬 프로세스 없음
- 프록시 IP 없음
- 메시지 큐 및 엑셀 파일 없음
"""
import time
import logging
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from crawler import NaverStoreCrawler
from config import Config
from test5 import create_click_result_script, setup_port_forwarding, get_mobile_external_ip_via_selenium #get_mobile_external_ip, 
from test6 import DataConnectionManager
from adb_manager import get_adb_manager
import pandas as pd
import threading
import requests  # 추가
# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
# 스레드별 포트 할당

THREAD_PORTS = [9222] 
SHARED_MOBILE_IP = None

def get_shared_mobile_ip(adb, driver=None):
    """모든 스레드가 공유하는 휴대폰 외부 IP 가져오기"""
    global SHARED_MOBILE_IP
    
    with IP_LOCK:
        if SHARED_MOBILE_IP is None:
            logger.info("휴대폰 외부 IP 확인 중...")
            
            # Selenium driver가 있으면 JavaScript로 IP 확인
            if driver is not None:
                from test5 import get_mobile_external_ip_via_selenium
                SHARED_MOBILE_IP = get_mobile_external_ip_via_selenium(driver)
            
            if SHARED_MOBILE_IP:
                logger.info(f"✓ 휴대폰 외부 IP 확인 성공: {SHARED_MOBILE_IP}")
            else:
                logger.warning("⚠ 휴대폰 외부 IP를 확인할 수 없습니다.")
                logger.warning("다음을 확인하세요:")
                logger.warning("1. 휴대폰에 인터넷 연결이 있는지")
                logger.warning("2. 휴대폰 Chrome이 정상적으로 실행 중인지")
        return SHARED_MOBILE_IP

def test_single_iteration(row_data, thread_id, port):
    """
    단일 반복 테스트
    
    Args:
        row_data: CSV 행 데이터 (pandas Series)
        thread_id: 스레드 ID
        port: 사용할 포트 번호
    """
    config = Config()
    crawler = None
    adb = None
    
    try:
        # 스레드별 ADB Manager 초기화
        adb = get_adb_manager()
        
        # ADB 연결 확인 (unauthorized 상태 체크 포함)
        if not adb.check_connection():
            logger.error(f"[스레드 {thread_id}] ADB 연결 실패. 크롤링을 중단합니다.")
            return False
        
        # IP 변경을 위해 데이터 연결 토글
        data_manager = DataConnectionManager(adb=adb)
        data_manager.toggle_data_connection(disable_duration=3)
        time.sleep(5)
        
        # 포트 포워딩 설정 (무조건 휴대폰 Chrome 사용)
        logger.info(f"[스레드 {thread_id}] 포트 포워딩 설정 중... (포트: {port})")
        port_forwarding_success = False
        max_retries = 3
        for retry in range(max_retries):
            if setup_port_forwarding(adb, port):
                port_forwarding_success = True
                break
            else:
                if retry < max_retries - 1:
                    logger.warning(f"[스레드 {thread_id}] 포트 포워딩 설정 실패, {retry + 1}/{max_retries} 재시도 중...")
                    # 재시도 전에 ADB 연결 상태 다시 확인
                    if not adb.check_connection():
                        logger.error(f"[스레드 {thread_id}] ADB 연결이 끊어졌습니다. 재시도를 중단합니다.")
                        return False
                    time.sleep(2)
                else:
                    logger.error(f"[스레드 {thread_id}] 포트 포워딩 설정 실패: 최대 재시도 횟수 초과")
                    logger.error(f"[스레드 {thread_id}] ADB 연결 상태를 확인하세요:")
                    logger.error(f"[스레드 {thread_id}] - 휴대폰에서 USB 디버깅 권한을 승인했는지 확인")
                    logger.error(f"[스레드 {thread_id}] - 휴대폰에서 Chrome이 실행 중인지 확인")
        
        if not port_forwarding_success:
            logger.error(f"[스레드 {thread_id}] 포트 포워딩 설정 실패로 인해 크롤링을 중단합니다.")
            return False
        
        # mobile_ip = get_mobile_external_ip(adb)
        import socket
        chrome_ready = False  # 초기화 추가
        for check_attempt in range(15):  # 최대 15번 확인 (약 7.5초)
            try:
                # 방법 1: 소켓으로 포트 확인
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(('127.0.0.1', port))
                sock.close()
                
                if result == 0:
                    # 방법 2: HTTP로 Chrome DevTools 확인 (더 정확함)
                    try:
                        response = requests.get(f'http://127.0.0.1:{port}/json', timeout=2)
                        if response.status_code == 200:
                            chrome_ready = True
                            logger.info(f"[스레드 {thread_id}] ✓ 포트 {port}에서 Chrome 연결 확인됨")
                            logger.info(f"[스레드 {thread_id}] Chrome DevTools 응답: {len(response.json())}개 타겟 발견")
                            break
                        else:
                            logger.debug(f"[스레드 {thread_id}] Chrome DevTools HTTP 응답 코드: {response.status_code}")
                    except requests.exceptions.RequestException as e:
                        logger.debug(f"[스레드 {thread_id}] Chrome DevTools HTTP 요청 실패: {e}")
                        # 포트는 열려있지만 Chrome DevTools가 아직 준비 안됨
                        pass
                else:
                    logger.debug(f"[스레드 {thread_id}] 포트 {port} 연결 실패 (소켓 결과: {result})")
                
                if check_attempt < 14:
                    logger.debug(f"[스레드 {thread_id}] Chrome 연결 대기 중... ({check_attempt + 1}/15)")
                    time.sleep(0.5)
            except Exception as e:
                logger.debug(f"[스레드 {thread_id}] 포트 연결 확인 중 오류: {e}")
                time.sleep(0.5)
        
        # Chrome 연결 확인 실패 시 중단
        if not chrome_ready:
            logger.error(f"[스레드 {thread_id}] 포트 {port}에서 Chrome을 찾을 수 없습니다.")
            logger.error(f"[스레드 {thread_id}] 다음을 확인하세요:")
            logger.error(f"[스레드 {thread_id}] 1. 휴대폰에서 Chrome이 실행 중인지 확인")
            logger.error(f"[스레드 {thread_id}] 2. 휴대폰에서 Chrome DevTools가 활성화되어 있는지 확인")
            logger.error(f"[스레드 {thread_id}] 3. 휴대폰에서 Chrome을 완전히 종료한 후 다시 실행해보세요")
            logger.error(f"[스레드 {thread_id}] 4. 다른 스레드가 같은 포트를 사용 중인지 확인")
            logger.error(f"[스레드 {thread_id}] 5. ADB 포트 포워딩 상태 확인: adb forward --list")
            return False

        mobile_ip = get_shared_mobile_ip(adb)
        if mobile_ip:
            logger.info(f"[스레드 {thread_id}] 휴대폰 외부 IP: {mobile_ip}")
        else:
            logger.warning(f"[스레드 {thread_id}] 휴대폰 외부 IP를 확인할 수 없습니다.")

        logger.info("=" * 50)
        logger.info(f"[스레드 {thread_id}] 테스트 시작")
        logger.info(f"[스레드 {thread_id}] 메인 키워드: {row_data['main_keyword']}")
        logger.info(f"[스레드 {thread_id}] 기본 검색 키워드: {row_data['base_search_keyword']}")
        logger.info(f"[스레드 {thread_id}] NV MID: {row_data['nv_mid']}")
        logger.info("=" * 50)
        
        # USE_REMOTE_DEVICE를 무조건 True로 설정하고, 각 스레드의 포트를 REMOTE_DEBUGGING_PORT로 설정
        original_use_remote = config.USE_REMOTE_DEVICE
        original_port = config.REMOTE_DEBUGGING_PORT
        
        config.USE_REMOTE_DEVICE = True  # 무조건 True로 설정
        config.REMOTE_DEBUGGING_PORT = port  # 각 스레드의 포트로 설정
        
        logger.info(f"[스레드 {thread_id}] USE_REMOTE_DEVICE: {config.USE_REMOTE_DEVICE}")
        logger.info(f"[스레드 {thread_id}] REMOTE_DEBUGGING_PORT: {config.REMOTE_DEBUGGING_PORT}")
        
        # 프록시 없이 크롤러 생성 (수정된 config 전달)
        crawler = NaverStoreCrawler(proxy_ip=None, config=config)
        
        # 네이버 접속
        crawler.navigate_to_naver()
            # 사람처럼 행동 (스텔스 모드 사용)
        if crawler.stealth:
            crawler.stealth.human_like_delay(1, 2)
        # WebDriver 속성 숨기기 봇감지
        try:
            crawler.driver.execute_script("""
                // 추가 WebDriver 속성 숨기기
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Chrome 객체 확인
                if (!window.navigator.chrome) {
                    window.navigator.chrome = {
                        runtime: {}
                    };
                }
            """)
        except:
            pass

        # 메인 키워드 검색 (CSV에서 가져온 값 사용)
        main_keyword = row_data['main_keyword']
        logger.info(f"[스레드 {thread_id}] 메인 키워드: {main_keyword}")
        crawler.search_main_keyword(main_keyword)
        
        # 검색어 지우고 새 검색어 입력 (CSV에서 가져온 값 사용)
        base_keyword = row_data['base_search_keyword']
        logger.info(f"[스레드 {thread_id}] 새 검색어: {base_keyword}")
        crawler.clear_search_and_input_new(base_keyword)

        # nvmid 기준으로 검색 결과 찾기 및 클릭
        try:
            before_url = crawler.driver.current_url
            logger.info(f"[스레드 {thread_id}] 클릭 전 URL: {before_url}")
            
            # CSV에서 가져온 nvmid 사용
            config_nvmid = str(row_data['nv_mid'])
            logger.info(f"[스레드 {thread_id}] NV MID 기준으로 검색 결과 찾기: {config_nvmid}")
            
            # test5의 create_click_result_script를 Selenium용으로 실행
            click_script = create_click_result_script(config_nvmid)
            result = crawler.driver.execute_script(click_script)
            
            if result and isinstance(result, dict) and result.get('success'):
                found_nvmid = result.get('nvmid')
                logger.info(f"[스레드 {thread_id}] ✓ NV MID 일치하는 검색 결과 클릭 완료: {found_nvmid}")
                debug_info = result.get('debug', {})
                if debug_info:
                    logger.info(f"[스레드 {thread_id}] 디버깅 정보 - 총 링크: {debug_info.get('totalLinks')}, 찾은 NV MID 목록: {debug_info.get('foundNvmids', [])[:10]}")
            else:
                reason = result.get('reason', 'unknown') if result and isinstance(result, dict) else 'unknown'
                debug_info = result.get('debug', {}) if result and isinstance(result, dict) else {}
                logger.warning(f"[스레드 {thread_id}] NV MID 일치하는 검색 결과를 찾지 못했습니다. 이유: {reason}")
                if debug_info:
                    logger.warning(f"[스레드 {thread_id}] 디버깅 정보 - 총 링크: {debug_info.get('totalLinks')}, 찾을 NV MID: {debug_info.get('targetNvmid')}, 찾은 NV MID 목록: {debug_info.get('foundNvmids', [])[:20]}")
            
            # 페이지 로드 대기 (URL 변경 확인)
            try:
                WebDriverWait(crawler.driver, 2).until(
                    lambda driver: driver.current_url != before_url
                )
                after_url = crawler.driver.current_url
                logger.info(f"[스레드 {thread_id}] 클릭 후 URL: {after_url}")
                logger.info(f"[스레드 {thread_id}] ✓ 링크 이동 성공")
            except:
                after_url = crawler.driver.current_url
                logger.warning(f"[스레드 {thread_id}] ⚠ URL 변경이 감지되지 않았습니다 (현재 URL: {after_url})")
            
            time.sleep(2)
        except Exception as e:
            logger.warning(f"[스레드 {thread_id}] 검색 결과 nvmid 기준 클릭 실패: {e}")
        
        # 제품 하단에 구매 추가정보 버튼 클릭
        crawler.click_purchase_additional_info()

        # 제품 하단에 구매 추가정보 버튼 클릭
        crawler.click_purchase_additional_info()

        logger.info(f"[스레드 {thread_id}] 테스트 완료")
        return True
        
    except Exception as e:
        logger.error(f"[스레드 {thread_id}] 테스트 중 오류 발생: {e}", exc_info=True)
        return False
    finally:
        if crawler:
            crawler.close()
        time.sleep(2)

def worker_thread(row_data, thread_id, port):
    """
    스레드 워커 함수
    
    Args:
        row_data: CSV 행 데이터 (pandas Series)
        thread_id: 스레드 ID
        port: 사용할 포트 번호
    """
    try:
        logger.info(f"[스레드 {thread_id}] 시작 (포트: {port})")
        success = test_single_iteration(row_data, thread_id, port)
        if success:
            logger.info(f"[스레드 {thread_id}] 성공")
        else:
            logger.warning(f"[스레드 {thread_id}] 실패")
    except Exception as e:
        logger.error(f"[스레드 {thread_id}] 스레드 실행 중 오류: {e}", exc_info=True)

def main():
    """메인 테스트 함수"""
    config = Config()
    
    logger.info("=" * 50)
    logger.info("네이버 스토어 크롤링 테스트 시작 (멀티스레드)")
    logger.info("=" * 50)
    
    # CSV 파일 읽기
    try:
        df = pd.read_csv('keyword_data.csv')
        logger.info(f"CSV 파일 로드 완료: {len(df)}개 행")
        logger.info(f"컬럼: {list(df.columns)}")
    except Exception as e:
        logger.error(f"CSV 파일 읽기 실패: {e}")
        return
    
    # 스레드 리스트
    threads = []
    
    # 각 행을 스레드로 처리 (최대 2개 스레드)
    for idx, row in df.iterrows():
        thread_id = idx + 1
        port = THREAD_PORTS[idx % len(THREAD_PORTS)]  # 포트 순환 할당
        
        logger.info(f"\n[행 {idx + 1}] 스레드 {thread_id} 생성 (포트: {port})")
        logger.info(f"  메인 키워드: {row['main_keyword']}")
        logger.info(f"  기본 검색 키워드: {row['base_search_keyword']}")
        logger.info(f"  NV MID: {row['nv_mid']}")
        
        # 스레드 생성 및 시작
        thread = threading.Thread(
            target=worker_thread,
            args=(row, thread_id, port),
            name=f"Thread-{thread_id}"
        )
        thread.start()
        threads.append(thread)
        
        # 최대 2개 스레드까지만 동시 실행
        if len(threads) >= 2:
            # 스레드가 완료될 때까지 대기
            for t in threads:
                t.join()
            threads = []
        
        # 스레드 간 시작 간격 (선택사항)
        time.sleep(2)
    
    # 남은 스레드들 대기
    for thread in threads:
        thread.join()
    
    logger.info("=" * 50)
    logger.info("모든 테스트 완료")
    logger.info("=" * 50)


if __name__ == '__main__':
    try:
        main()
        logger.info("프로그램 정상 종료")
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단됨")
    except Exception as e:
        logger.error(f"프로그램 실행 중 오류: {e}", exc_info=True)
    finally:
        logger.info("프로그램 종료")

