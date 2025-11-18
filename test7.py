"""
기존 test7.py에 통합 가능한 봇 탐지 회피 버전
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
import threading
import undetected_chromedriver as uc
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 스레드별 포트 할당
THREAD_PORTS = [9222, 9223]

# 전역 변수로 IP 저장
SHARED_MOBILE_IP = None
IP_LOCK = threading.Lock()
DRIVER_INIT_LOCK = threading.Lock()  # 드라이버 초기화용 락
# 여러 스레드가 동시에 undetected-chromedriver를 사용할 때 파일 충돌 방지를 위해 락 사용

class StealthNaverCrawler:
    """봇 탐지 회피 기능이 강화된 네이버 크롤러"""
    
    def __init__(self, port=9222):
        self.driver = None
        self.port = port
        self._setup_stealth_driver()
    
    def _setup_stealth_driver(self):
        """스텔스 드라이버 설정"""
        options = uc.ChromeOptions()
        
        # 모바일 Chrome 원격 디버깅
        options.add_experimental_option("debuggerAddress", f"127.0.0.1:{self.port}")
        
        # undetected-chromedriver는 자동으로 자동화 탐지 회피 옵션을 처리하므로
        # excludeSwitches와 useAutomationExtension은 제거
        # options.add_experimental_option("excludeSwitches", ["enable-automation"])
        # options.add_experimental_option('useAutomationExtension', False)
        
        # 여러 스레드가 동시에 드라이버를 초기화할 때 파일 충돌 방지를 위해 락 사용
        with DRIVER_INIT_LOCK:
            # undetected-chromedriver로 드라이버 생성
            self.driver = uc.Chrome(options=options, version_main=None)
        
        # 스텔스 스크립트 주입
        self._apply_stealth_scripts()
        
        logger.info(f"✓ 스텔스 드라이버 초기화 (포트: {self.port})")
    
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


def test_single_iteration_stealth(row_data, thread_id, port):
    """
    봇 탐지 회피 기능이 추가된 단일 반복 테스트
    """
    crawler = None
    adb = None
    
    try:
        # ADB Manager 초기화
        adb = get_adb_manager()
        
        if not adb.check_connection():
            logger.error(f"[스레드 {thread_id}] ADB 연결 실패")
            return False
        
        # IP 변경
        data_manager = DataConnectionManager(adb=adb)
        data_manager.toggle_data_connection(disable_duration=3)
        time.sleep(5)
        
        # 포트 포워딩 (재시도 로직 포함)
        port_forwarding_success = False
        max_retries = 3
        for retry in range(max_retries):
            # 스레드 안전성을 위해 락 사용
            with IP_LOCK:
                if setup_port_forwarding(adb, port):
                    port_forwarding_success = True
                    break
                else:
                    if retry < max_retries - 1:
                        logger.warning(f"[스레드 {thread_id}] 포트 포워딩 설정 실패, {retry + 1}/{max_retries} 재시도 중... (포트: {port})")
                        if not adb.check_connection():
                            logger.error(f"[스레드 {thread_id}] ADB 연결이 끊어졌습니다.")
                            return False
                        time.sleep(2)
                    else:
                        logger.error(f"[스레드 {thread_id}] 포트 포워딩 설정 실패: 최대 재시도 횟수 초과 (포트: {port})")
        
        if not port_forwarding_success:
            logger.error(f"[스레드 {thread_id}] 포트 포워딩 설정 실패로 인해 크롤링을 중단합니다. (포트: {port})")
            return False
        
        # Chrome DevTools 연결 확인 (세션 생성 가능 여부 확인)
        logger.info(f"[스레드 {thread_id}] Chrome DevTools 연결 확인 중... (포트: {port})")
        chrome_ready = False
        max_chrome_check_attempts = 20  # 최대 20번 확인 (약 10초)
        
        for check_attempt in range(max_chrome_check_attempts):
            try:
                # 방법 1: 소켓으로 포트 연결 확인
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                socket_result = sock.connect_ex(('127.0.0.1', port))
                sock.close()
                
                if socket_result == 0:
                    # 방법 2: HTTP로 Chrome DevTools API 확인 (세션 생성 가능 여부)
                    try:
                        response = requests.get(f'http://127.0.0.1:{port}/json', timeout=3)
                        if response.status_code == 200:
                            targets = response.json()
                            if targets:
                                chrome_ready = True
                                logger.info(f"[스레드 {thread_id}] ✓ Chrome DevTools 연결 확인됨 (포트: {port})")
                                logger.info(f"[스레드 {thread_id}]   - 발견된 타겟 수: {len(targets)}개")
                                
                                # 타겟 정보 로깅
                                for idx, target in enumerate(targets[:3]):  # 최대 3개만 로깅
                                    target_type = target.get('type', 'unknown')
                                    target_title = target.get('title', 'Unknown')[:50]
                                    target_url = target.get('url', 'N/A')[:50]
                                    logger.info(f"[스레드 {thread_id}]   - 타겟 {idx+1}: {target_type} - {target_title} ({target_url})")
                                
                                if len(targets) > 3:
                                    logger.info(f"[스레드 {thread_id}]   - ... 외 {len(targets)-3}개 타겟")
                                break
                            else:
                                logger.warning(f"[스레드 {thread_id}] Chrome DevTools API 응답은 받았지만 타겟이 없습니다. (포트: {port})")
                                logger.warning(f"[스레드 {thread_id}]   - 휴대폰에서 Chrome이 실행 중인지 확인하세요.")
                        else:
                            logger.debug(f"[스레드 {thread_id}] Chrome DevTools HTTP 응답 코드: {response.status_code} (포트: {port})")
                    except requests.exceptions.ConnectionError as e:
                        logger.debug(f"[스레드 {thread_id}] Chrome DevTools 연결 실패 (포트: {port}): {e}")
                        logger.debug(f"[스레드 {thread_id}]   - 포트는 열려있지만 Chrome DevTools가 아직 준비되지 않았습니다.")
                    except requests.exceptions.Timeout as e:
                        logger.debug(f"[스레드 {thread_id}] Chrome DevTools 요청 타임아웃 (포트: {port}): {e}")
                    except Exception as e:
                        logger.debug(f"[스레드 {thread_id}] Chrome DevTools 확인 중 오류 (포트: {port}): {e}")
                else:
                    logger.debug(f"[스레드 {thread_id}] 포트 {port} 소켓 연결 실패 (결과 코드: {socket_result})")
                
                if check_attempt < max_chrome_check_attempts - 1:
                    logger.debug(f"[스레드 {thread_id}] Chrome 연결 대기 중... ({check_attempt + 1}/{max_chrome_check_attempts})")
                    time.sleep(0.5)
            except Exception as e:
                logger.debug(f"[스레드 {thread_id}] 포트 연결 확인 중 오류 (포트: {port}): {e}")
                time.sleep(0.5)
        
        # Chrome 연결 확인 실패 시 상세 정보 로깅
        if not chrome_ready:
            logger.error(f"[스레드 {thread_id}] ✗ Chrome DevTools 연결 실패 (포트: {port})")
            
            # 포트 상태 재확인
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                socket_result = sock.connect_ex(('127.0.0.1', port))
                sock.close()
                
                if socket_result == 0:
                    logger.error(f"[스레드 {thread_id}]   - 포트 {port}는 열려있지만 Chrome DevTools API에 접근할 수 없습니다.")
                    try:
                        response = requests.get(f'http://127.0.0.1:{port}/json', timeout=2)
                        logger.error(f"[스레드 {thread_id}]   - HTTP 응답 코드: {response.status_code}")
                        logger.error(f"[스레드 {thread_id}]   - 응답 내용: {response.text[:200]}")
                    except Exception as e:
                        logger.error(f"[스레드 {thread_id}]   - HTTP 요청 실패: {e}")
                else:
                    logger.error(f"[스레드 {thread_id}]   - 포트 {port}가 열려있지 않습니다.")
            except Exception as e:
                logger.error(f"[스레드 {thread_id}]   - 포트 상태 확인 실패: {e}")
            
            return False
        

        
        # 스텔스 크롤러 생성
        crawler = StealthNaverCrawler(port=port)
        
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
        
        # 페이지에서 랜덤 행동
        for _ in range(2):
            crawler.random_behavior()
        
        logger.info(f"[스레드 {thread_id}] 스텔스 크롤링 완료")
        return True
        
    except Exception as e:
        logger.error(f"[스레드 {thread_id}] 오류: {e}", exc_info=True)
        return False
    finally:
        if crawler:
            crawler.close()
        time.sleep(2)


def worker_thread_stealth(row_data, thread_id, port):
    """스텔스 워커 스레드"""
    try:
        logger.info(f"[스레드 {thread_id}] 시작 (포트: {port})")
        success = test_single_iteration_stealth(row_data, thread_id, port)
        if success:
            logger.info(f"[스레드 {thread_id}] 성공")
        else:
            logger.warning(f"[스레드 {thread_id}] 실패")
    except Exception as e:
        logger.error(f"[스레드 {thread_id}] 오류: {e}", exc_info=True)


def test_libraries():
    """Beautiful Soup과 undetected_chromedriver 작동 테스트"""
    logger.info("=" * 50)
    logger.info("라이브러리 작동 테스트 시작")
    logger.info("=" * 50)
    
    # 1. Beautiful Soup 테스트
    logger.info("\n[1] Beautiful Soup 테스트...")
    try:
        html = """
        <html>
            <head><title>Test Page</title></head>
            <body>
                <div class="test">Hello World</div>
                <a href="https://example.com">Link</a>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, 'html.parser')
        title = soup.find('title').text
        div_text = soup.find('div', class_='test').text
        link = soup.find('a')['href']
        
        logger.info(f"✓ Beautiful Soup 작동 확인")
        logger.info(f"  - Title: {title}")
        logger.info(f"  - Div text: {div_text}")
        logger.info(f"  - Link: {link}")
    except Exception as e:
        logger.error(f"✗ Beautiful Soup 테스트 실패: {e}")
        return False
    
    # 2. undetected_chromedriver 테스트
    logger.info("\n[2] undetected_chromedriver 테스트...")
    driver = None
    try:
        options = uc.ChromeOptions()
        options.add_argument('--headless')  # 헤드리스 모드로 테스트
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        driver = uc.Chrome(options=options, version_main=None)
        driver.get("https://www.google.com")
        
        # 페이지 제목 확인
        title = driver.title
        logger.info(f"✓ undetected_chromedriver 작동 확인")
        logger.info(f"  - 페이지 제목: {title}")
        logger.info(f"  - 현재 URL: {driver.current_url}")
        
        # Beautiful Soup과 함께 사용 테스트
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        logger.info(f"✓ Beautiful Soup과 undetected_chromedriver 함께 사용 가능")
        
        driver.quit()
        logger.info("\n" + "=" * 50)
        logger.info("✓ 모든 라이브러리 테스트 통과!")
        logger.info("=" * 50)
        return True
        
    except Exception as e:
        logger.error(f"✗ undetected_chromedriver 테스트 실패: {e}")
        if driver:
            try:
                driver.quit()
            except:
                pass
        return False


def main():
    """메인 함수"""
    logger.info("=" * 50)
    logger.info("스텔스 네이버 크롤러 시작")
    logger.info("=" * 50)
    
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
    
    threads = []
    
    for idx, row in df.iterrows():
        thread_id = idx + 1
        port = THREAD_PORTS[idx % len(THREAD_PORTS)]
        
        thread = threading.Thread(
            target=worker_thread_stealth,
            args=(row, thread_id, port),
            name=f"Thread-{thread_id}"
        )
        thread.start()
        threads.append(thread)
        
        if len(threads) >= 2:
            for t in threads:
                t.join()
            threads = []
        
        time.sleep(2)
    
    for thread in threads:
        thread.join()
    
    logger.info("=" * 50)
    logger.info("모든 크롤링 완료")
    logger.info("=" * 50)


if __name__ == '__main__':
    # 라이브러리 테스트 먼저 실행
    if test_libraries():
        logger.info("\n라이브러리 테스트 완료. 메인 함수를 실행하려면 주석을 해제하세요.\n")
        main()  # 메인 함수 실행하려면 주석 해제
    else:
        logger.error("\n라이브러리 테스트 실패. 문제를 해결한 후 다시 시도하세요.")