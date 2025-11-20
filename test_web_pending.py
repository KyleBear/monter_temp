#### 현재 IP 로 셀레니움 + 스텔스 모드 크롤링 테스트 를 하는 코드 ####
#### 일단 셀레니움 + 스텔스 스크립트 병함 되는지 확인 #### 
#### csv 파일의 행만큼 인스턴스 열고, 각 인스턴스 마다 test_iteration 함수 실행 ####

import time
import logging
import random
import pandas as pd
import os
import subprocess
import platform
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.alert import Alert
from selenium import webdriver
from test5 import create_click_result_script
from test6 import DataConnectionManager
from adb_manager import get_adb_manager
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ip 변경으로 + 브라우저 + 변경 확인
def change_ip(disable_duration=3):
    """
    IP 변경을 위해 데이터 연결을 끄고 켜기
    
    Args:
        disable_duration: 데이터를 끈 상태로 유지할 시간(초), 기본값: 3초
    
    Returns:
        bool: 성공 여부
    """
    try:
        logger.info(f"[IP 변경] IP 변경 시작 (데이터 연결 끄기 시간: {disable_duration}초)")
        
        # ADB Manager 초기화
        adb = get_adb_manager()
        
        # ADB 연결 확인
        if not adb.check_connection():
            logger.error(f"[IP 변경] ADB 연결 실패. IP 변경을 건너뜁니다.")
            return False
        
        # DataConnectionManager 생성
        data_manager = DataConnectionManager(adb=adb)
        
        # 데이터 연결 토글 (끄기 → 대기 → 켜기)
        success = data_manager.toggle_data_connection(disable_duration=disable_duration)
        
        if success:
            logger.info(f"[IP 변경] ✓ IP 변경 완료")
            # 네트워크 재연결 대기
            time.sleep(5)
            return True
        else:
            logger.warning(f"[IP 변경] ⚠ IP 변경 실패 (계속 진행)")
            return False
            
    except Exception as e:
        logger.error(f"[IP 변경] IP 변경 중 오류: {e}", exc_info=True)
        return False


class StealthNaverCrawler:
    """봇 탐지 회피 기능이 강화된 네이버 크롤러 (로컬 Chrome)"""
    
    def __init__(self, instance_id=None, headless=False):
        logger.info(f"[StealthNaverCrawler] 초기화 시작 (인스턴스 ID: {instance_id})")
        self.driver = None
        self.instance_id = instance_id
        try:
            self._setup_stealth_driver(headless)
            logger.info(f"[StealthNaverCrawler] 초기화 완료 (인스턴스 ID: {instance_id})")
        except Exception as e:
            logger.error(f"[StealthNaverCrawler] 초기화 실패 (인스턴스 ID: {instance_id}): {e}", exc_info=True)
            raise
    
    def _setup_stealth_driver(self, headless=False):
        """스텔스 드라이버 설정"""
        logger.info(f"[_setup_stealth_driver] 시작 (인스턴스 ID: {self.instance_id})")
        
        # Chrome 옵션 설정
        options = Options()
        
        # 스텔스 모드 옵션
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Headless 모드 (선택사항)
        if headless:
            options.add_argument('--headless=new')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
        
        # 스텔스 설정
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # 각 인스턴스별 독립적인 사용자 데이터
        user_data_dir = None
        if self.instance_id:
            # 절대 경로로 변환하여 잠금 문제 방지
            user_data_dir = os.path.abspath(f"chrome_data_{self.instance_id}")
            options.add_argument(f'--user-data-dir={user_data_dir}')
            
            # 이전 세션 잠금 파일 정리 시도
            self._cleanup_user_data_lock(user_data_dir)
        else:
            # instance_id가 없으면 임시 디렉토리 사용 (세션 간 격리)
            import tempfile
            user_data_dir = tempfile.mkdtemp(prefix='chrome_data_')
            options.add_argument(f'--user-data-dir={user_data_dir}')
        
        # WebDriver 생성 (재시도 로직 포함)
        service = Service()
        max_retries = 2
        last_error = None
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    logger.info(f"[_setup_stealth_driver] 재시도 {attempt + 1}/{max_retries}...")
                    # 재시도 전 잠금 파일 다시 정리
                    if user_data_dir:
                        self._cleanup_user_data_lock(user_data_dir)
                        time.sleep(1)
                
                logger.info(f"[_setup_stealth_driver] Chrome WebDriver 생성 시도 중... (user_data_dir: {user_data_dir})")
                self.driver = webdriver.Chrome(service=service, options=options)
                logger.info(f"[_setup_stealth_driver] Chrome WebDriver 생성 성공")
                break  # 성공 시 루프 종료
                
            except Exception as e:
                last_error = e
                error_msg = str(e)
                logger.error(f"[_setup_stealth_driver] Chrome WebDriver 생성 실패 (시도 {attempt + 1}/{max_retries}): {error_msg}")
                
                # "Chrome instance exited" 오류 특별 처리
                if 'instance exited' in error_msg.lower() or 'session not created' in error_msg.lower():
                    logger.error(f"[_setup_stealth_driver] Chrome 인스턴스 종료 오류 감지")
                    logger.error(f"[_setup_stealth_driver] 원인 분석:")
                    logger.error(f"  1. 같은 user_data_dir를 사용하는 Chrome 프로세스가 이미 실행 중일 수 있습니다")
                    logger.error(f"  2. 이전에 종료되지 않은 Chrome 프로세스가 남아있을 수 있습니다")
                    logger.error(f"  3. user_data_dir 디렉토리가 잠겨있거나 손상되었을 수 있습니다")
                    logger.error(f"  4. ChromeDriver와 Chrome 버전이 일치하지 않을 수 있습니다")
                    
                    if attempt < max_retries - 1:
                        logger.warning(f"[_setup_stealth_driver] 재시도 전 user_data_dir 정리 중...")
                        # user_data_dir 정리 시도
                        if user_data_dir and os.path.exists(user_data_dir):
                            try:
                                # 잠금 파일 삭제
                                self._cleanup_user_data_lock(user_data_dir)
                                # 잠시 대기
                                time.sleep(2)
                            except:
                                pass
                    else:
                        logger.error(f"[_setup_stealth_driver] 해결 방법:")
                        logger.error(f"  1. 실행 중인 Chrome 프로세스 확인 및 종료")
                        logger.error(f"  2. user_data_dir 디렉토리 삭제 후 재시도")
                        logger.error(f"  3. ChromeDriver 버전 확인 (Chrome 버전과 일치해야 함)")
                
                # 마지막 시도가 아니면 재시도
                if attempt < max_retries - 1:
                    continue
                else:
                    # 모든 재시도 실패
                    raise last_error
        
        # 스텔스 스크립트 주입
        self._inject_stealth_scripts()
        
        logger.info(f"[_setup_stealth_driver] 드라이버 생성 완료 (인스턴스 ID: {self.instance_id})")
    
    def _cleanup_user_data_lock(self, user_data_dir):
        """user_data_dir의 잠금 파일 정리"""
        try:
            if not os.path.exists(user_data_dir):
                return
            
            # SingletonLock 파일 삭제 시도
            lock_file = os.path.join(user_data_dir, 'SingletonLock')
            if os.path.exists(lock_file):
                try:
                    os.remove(lock_file)
                    logger.debug(f"[_cleanup_user_data_lock] 잠금 파일 삭제: {lock_file}")
                except Exception as e:
                    logger.debug(f"[_cleanup_user_data_lock] 잠금 파일 삭제 실패: {e}")
            
            # LockFile 파일 삭제 시도
            lock_file2 = os.path.join(user_data_dir, 'Default', 'LockFile')
            if os.path.exists(lock_file2):
                try:
                    os.remove(lock_file2)
                    logger.debug(f"[_cleanup_user_data_lock] LockFile 삭제: {lock_file2}")
                except Exception as e:
                    logger.debug(f"[_cleanup_user_data_lock] LockFile 삭제 실패: {e}")
        except Exception as e:
            logger.debug(f"[_cleanup_user_data_lock] 정리 중 오류: {e}")
    
    def _kill_chrome_processes(self, user_data_dir=None):
        """Chrome 프로세스 종료 (Windows)"""
        try:
            if platform.system() != 'Windows':
                return
            
            # user_data_dir를 사용하는 Chrome 프로세스 찾기
            if user_data_dir:
                # user_data_dir를 사용하는 프로세스는 직접 종료하기 어려우므로
                # 모든 Chrome 프로세스를 종료하는 것은 위험할 수 있음
                # 대신 잠금 파일만 정리
                return
            
            # Chrome 프로세스 확인 (디버깅용)
            try:
                result = subprocess.run(
                    ['tasklist', '/FI', 'IMAGENAME eq chrome.exe'],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if result.returncode == 0 and 'chrome.exe' in result.stdout:
                    chrome_count = result.stdout.count('chrome.exe')
                    if chrome_count > 0:
                        logger.debug(f"[_kill_chrome_processes] 실행 중인 Chrome 프로세스: {chrome_count}개")
            except:
                pass
        except Exception as e:
            logger.debug(f"[_kill_chrome_processes] 프로세스 확인 중 오류: {e}")
    
    def _inject_stealth_scripts(self):
        """봇 탐지 회피 스크립트 주입"""
        stealth_js = """
        // Navigator 속성 조작
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        
        // Chrome 객체 추가
        window.navigator.chrome = {
            runtime: {},
            loadTimes: function() {},
            csi: function() {},
            app: {}
        };
        
        // Plugins 속성 조작
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });
        
        // Languages 속성 조작
        Object.defineProperty(navigator, 'languages', {
            get: () => ['ko-KR', 'ko', 'en-US', 'en']
        });
        
        // Permissions 조작
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        
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
            logger.error(f"구매 추가정보 클릭 실패: {e}")
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


def test_single_iteration(row_data, iteration_id, headless=False):
    """
    단일 반복 테스트 함수 (test8의 test_single_iteration_stealth 구조 참고)
    
    Args:
        row_data: CSV 행 데이터 (pandas Series)
        iteration_id: 반복 ID
        headless: Headless 모드 사용 여부
    
    Returns:
        bool: 성공 여부
    """
    crawler = None
    
    try:
        logger.info(f"[반복 {iteration_id}] ========================================")
        logger.info(f"[반복 {iteration_id}] 스텔스 크롤러 생성 시작")
        logger.info(f"[반복 {iteration_id}] ========================================")
        
        # 스텔스 크롤러 생성
        try:
            crawler = StealthNaverCrawler(instance_id=iteration_id, headless=headless)
            logger.info(f"[반복 {iteration_id}] ✓ 스텔스 크롤러 생성 완료")
        except Exception as e:
            logger.error(f"[반복 {iteration_id}] ✗ 스텔스 크롤러 생성 실패: {e}", exc_info=True)
            return False
        
        # 네이버 접속
        crawler.navigate_to_naver()
        
        # 랜덤 행동
        crawler.random_behavior()
        
        # 메인 키워드 검색
        if 'main_keyword' in row_data and pd.notna(row_data['main_keyword']):
            crawler.search_keyword(row_data['main_keyword'])
        
        # 랜덤 행동
        crawler.random_behavior()
        
        # 새 검색어로 검색
        if 'base_search_keyword' in row_data and pd.notna(row_data['base_search_keyword']):
            crawler.search_keyword(row_data['base_search_keyword'])
        
        # 랜덤 행동
        crawler.random_behavior()
        
        # nvmid로 상품 클릭
        if 'nv_mid' in row_data and pd.notna(row_data['nv_mid']):
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


def main():
    """메인 함수"""
    logger.info("=" * 50)
    logger.info("셀레니움 + 스텔스 모드 크롤링 테스트 시작")
    logger.info("=" * 50)
    change_ip()
    time.sleep(4)
    # CSV 파일 경로
    csv_file = 'keyword_data.csv'
    
    if not os.path.exists(csv_file):
        logger.error(f"CSV 파일을 찾을 수 없습니다: {csv_file}")
        logger.info("CSV 파일 형식:")
        logger.info("  - main_keyword: 메인 키워드")
        logger.info("  - base_search_keyword: 새 검색어")
        logger.info("  - nv_mid: 상품 ID")
        return
    
    # CSV 로드
    encodings = ['cp949', 'euc-kr', 'utf-8', 'latin-1']
    df = None
    
    for encoding in encodings:
        try:
            df = pd.read_csv(csv_file, encoding=encoding)
            logger.info(f"CSV 로드 성공 (인코딩: {encoding}): {len(df)}개 행")
            break
        except:
            continue
    
    if df is None:
        logger.error("CSV 파일을 읽을 수 없습니다")
        return
    
    # 각 행마다 테스트 실행 (test8의 구조처럼)
    # try:
    #     for idx, row in df.iterrows():
    #         iteration_id = idx + 1
            
    #         logger.info("=" * 50)
    #         logger.info(f"[반복 {iteration_id}/{len(df)}] 시작")
    #         logger.info("=" * 50)
            
    #         success = test_single_iteration(row, iteration_id, headless=False)
    #         if success:
    #             logger.info(f"[반복 {iteration_id}] ✓ 성공")
    #         else:
    #             logger.warning(f"[반복 {iteration_id}] ✗ 실패")
            
    #         # 다음 반복 전 대기
    #         if idx < len(df) - 1:  # 마지막 반복이 아니면
    #             logger.info(f"[반복 {iteration_id}] 다음 반복 전 2초 대기...")
    #             time.sleep(2)
        
    #     logger.info("=" * 50)
    #     logger.info("모든 크롤링 완료")
    #     logger.info("=" * 50)
        
    # except Exception as e:
    #     logger.error(f"크롤링 중 오류: {e}", exc_info=True)

    # 병렬 크롤링 실행 (0.5초 딜레이로 여러 Chrome 인스턴스 동시 생성)
    max_workers = 5  # 동시 실행할 최대 작업 수 (필요에 따라 조정)
    
    try:
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            
            # 모든 작업을 스레드 풀에 제출 (0.5초 딜레이로)
            for idx, row in df.iterrows():
                iteration_id = idx + 1
                
                # 0.5초 딜레이를 주면서 작업 제출
                if idx > 0:
                    time.sleep(0.5)
                
                logger.info(f"[작업 제출] 반복 {iteration_id}/{len(df)} 작업 제출 중...")
                future = executor.submit(test_single_iteration, row, iteration_id, False)
                futures.append((future, iteration_id))
            
            logger.info(f"[병렬 실행] 총 {len(futures)}개 작업이 {max_workers}개 스레드로 병렬 실행됩니다")
            
            # 완료된 작업 결과 수집
            for future, iteration_id in futures:
                try:
                    success = future.result(timeout=300)  # 최대 5분 타임아웃
                    results.append({
                        'success': success,
                        'iteration_id': iteration_id
                    })
                    
                    if success:
                        logger.info(f"✓ [반복 {iteration_id}] 성공")
                    else:
                        logger.warning(f"✗ [반복 {iteration_id}] 실패")
                except Exception as e:
                    logger.error(f"✗ [반복 {iteration_id}] 작업 실행 중 오류: {e}", exc_info=True)
                    results.append({
                        'success': False,
                        'iteration_id': iteration_id,
                        'error': str(e)
                    })
        
        # 결과 요약
        success_count = sum(1 for r in results if r.get('success'))
        logger.info("=" * 50)
        logger.info(f"모든 크롤링 완료: {success_count}/{len(results)} 성공")
        logger.info("=" * 50)
        
        # 실패한 항목 출력
        failed = [r for r in results if not r.get('success')]
        if failed:
            logger.warning(f"\n실패한 항목 ({len(failed)}개):")
            for r in failed:
                logger.warning(f"  - 반복 {r['iteration_id']}: {r.get('error', '알 수 없는 오류')}")
        
    except Exception as e:
        logger.error(f"크롤링 중 오류: {e}", exc_info=True)

if __name__ == '__main__':
    main()
