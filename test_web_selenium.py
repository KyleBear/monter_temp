#### 현재 IP 로 일반 셀레니움 크롤링 테스트 를 하는 코드 ####
#### csv 파일의 행만큼 인스턴스 열고, 각 인스턴스 마다 test_iteration 함수 실행 ####

import time
import logging
import random
import pandas as pd
import os
import subprocess
import platform
import shutil
import tempfile
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


class NaverCrawler:
    """일반 셀레니움 네이버 크롤러 (로컬 Chrome)"""
    
    def __init__(self, instance_id=None, headless=False):
        logger.info(f"[NaverCrawler] 초기화 시작 (인스턴스 ID: {instance_id})")
        self.driver = None
        self.instance_id = instance_id
        try:
            self._setup_driver(headless)
            logger.info(f"[NaverCrawler] 초기화 완료 (인스턴스 ID: {instance_id})")
        except Exception as e:
            logger.error(f"[NaverCrawler] 초기화 실패 (인스턴스 ID: {instance_id}): {e}", exc_info=True)
            raise
    
    def _setup_driver(self, headless=False):
        """일반 셀레니움 드라이버 설정"""
        logger.info(f"[_setup_driver] 시작 (인스턴스 ID: {self.instance_id})")
        
        # Chrome 옵션 설정
        options = Options()
        
        # 기본 옵션
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36')
        
        # 자동화 탐지 제거 옵션 
        # === [자동화 흔적 제거 필수 옵션] ===
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        # Chrome 로그 오류 억제 (GCM 등록 오류 등)
        options.add_argument("--disable-logging")
        options.add_argument("--log-level=3")  # INFO 레벨 이상만 표시 (ERROR, FATAL 숨김)
        options.add_argument("--disable-gcm")  # GCM 서비스 비활성화 (QUOTA_EXCEEDED 오류 방지)
        
        # Client Hints + 브라우저 fingerprint 패턴까지 체크도 추가 
        # navigator webdriver checke 확인.

        # Headless 모드 (선택사항)
        if headless:
            options.add_argument('--headless=new')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
        
        # 각 인스턴스별 독립적인 사용자 데이터
        user_data_dir = None
        if self.instance_id:
            # 절대 경로로 변환하여 잠금 문제 방지
            # 크롬 캐시 파일 저장
            # user_data_dir = os.path.abspath(f"chrome_data_{self.instance_id}")
            # options.add_argument(f'--user-data-dir={user_data_dir}')
            
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
                    logger.info(f"[_setup_driver] 재시도 {attempt + 1}/{max_retries}...")
                    # 재시도 전 잠금 파일 다시 정리
                    if user_data_dir:
                        self._cleanup_user_data_lock(user_data_dir)
                        time.sleep(1)
                
                logger.info(f"[_setup_driver] Chrome WebDriver 생성 시도 중... (user_data_dir: {user_data_dir})")
                self.driver = webdriver.Chrome(service=service, options=options)
                logger.info(f"[_setup_driver] Chrome WebDriver 생성 성공")
                break  # 성공 시 루프 종료
                
            except Exception as e:
                last_error = e
                error_msg = str(e)
                logger.error(f"[_setup_driver] Chrome WebDriver 생성 실패 (시도 {attempt + 1}/{max_retries}): {error_msg}")
                
                # "Chrome instance exited" 오류 특별 처리
                if 'instance exited' in error_msg.lower() or 'session not created' in error_msg.lower():
                    logger.error(f"[_setup_driver] Chrome 인스턴스 종료 오류 감지")
                    logger.error(f"[_setup_driver] 원인 분석:")
                    logger.error(f"  1. 같은 user_data_dir를 사용하는 Chrome 프로세스가 이미 실행 중일 수 있습니다")
                    logger.error(f"  2. 이전에 종료되지 않은 Chrome 프로세스가 남아있을 수 있습니다")
                    logger.error(f"  3. user_data_dir 디렉토리가 잠겨있거나 손상되었을 수 있습니다")
                    logger.error(f"  4. ChromeDriver와 Chrome 버전이 일치하지 않을 수 있습니다")
                    
                    if attempt < max_retries - 1:
                        logger.warning(f"[_setup_driver] 재시도 전 user_data_dir 정리 중...")
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
                        logger.error(f"[_setup_driver] 해결 방법:")
                        logger.error(f"  1. 실행 중인 Chrome 프로세스 확인 및 종료")
                        logger.error(f"  2. user_data_dir 디렉토리 삭제 후 재시도")
                        logger.error(f"  3. ChromeDriver 버전 확인 (Chrome 버전과 일치해야 함)")
                
                # 마지막 시도가 아니면 재시도
                if attempt < max_retries - 1:
                    continue
                else:
                    # 모든 재시도 실패
                    raise last_error
        
        logger.info(f"[_setup_driver] 드라이버 생성 완료 (인스턴스 ID: {self.instance_id})")
    
    def enable_mobile_mode(self):
        """모바일 모드로 전환 (F12 Toggle Device Toolbar와 동일) - Selenium CDP 사용"""
        try:
            logger.info("모바일 모드로 전환 중...")
            # 1,2,3 크롬 토글 Device Toolbar 와 동일.
            # 1. User-Agent를 모바일로 변경
            mobile_user_agent = "Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.7444.175 Mobile Safari/537.36"
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                'userAgent': mobile_user_agent,
                'acceptLanguage': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
                'platform': 'Linux armv8l'
            })
            logger.info("✓ User-Agent를 모바일로 변경 완료")
            
            # 2. 뷰포트를 모바일로 설정
            self.driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
                'width': 375,
                'height': 667,
                'deviceScaleFactor': 2.0,
                'mobile': True,
                'screenOrientation': {'angle': 0, 'type': 'portraitPrimary'}  # ← 추가
            })
            logger.info("✓ 뷰포트를 모바일로 설정 완료 (375x667)")
            
            # 3. 터치 이벤트 활성화
            self.driver.execute_cdp_cmd('Emulation.setTouchEmulationEnabled', {
                'enabled': True,
                'maxTouchPoints': 5
            })
            logger.info("✓ 터치 이벤트 활성화 완료")
            
            # 4. ⭐ 중요: Emulation.setEmulatedMedia 설정
            self.driver.execute_cdp_cmd('Emulation.setEmulatedMedia', {
                'media': 'screen',
                'features': [
                    {'name': 'prefers-color-scheme', 'value': 'light'},
                    {'name': 'prefers-reduced-motion', 'value': 'no-preference'}
                ]
            })
            logger.info("✓ Media 설정 완료")
            
            # 5. ⭐ Client Hints 설정 (최신 Chrome에서 중요!)
            self.driver.execute_cdp_cmd('Emulation.setUserAgentOverride', {
                'userAgent': mobile_user_agent,
                'acceptLanguage': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
                'platform': 'Linux armv8l',
                'userAgentMetadata': {  # ← 이게 핵심!
                    'brands': [
                        {'brand': 'Chromium', 'version': '142'},
                        {'brand': 'Google Chrome', 'version': '142'},
                        {'brand': 'Not_A Brand', 'version': '99'}
                    ],
                    'fullVersionList': [
                        {'brand': 'Chromium', 'version': '142.0.7444.175'},
                        {'brand': 'Google Chrome', 'version': '142.0.7444.175'},
                        {'brand': 'Not_A Brand', 'version': '99.0.0.0'}
                    ],
                    'fullVersion': '142.0.7444.175',
                    'platform': 'Android',
                    'platformVersion': '10.0.0',
                    'architecture': 'arm',
                    'model': 'SM-G973F',
                    'mobile': True,
                    'bitness': '64'
                }
            })
            logger.info("✓ Client Hints 설정 완료")
            
            # 6. ⭐ Pointer 타입 설정
            self.driver.execute_cdp_cmd('Emulation.setEmitTouchEventsForMouse', {
                'enabled': True,
                'configuration': 'mobile'
            })
            logger.info("✓ Touch 마우스 이벤트 변환 완료")
            
            return True
        except Exception as e:
            logger.error(f"모바일 모드 전환 실패: {e}", exc_info=True)
            return False

    def clear_search(self):
        """검색어 삭제 버튼 클릭"""
        logger.info("검색어 삭제 중...")
        try:
            clear_and_search_script = """
            (function() {
                var clearBtn = document.querySelector('button[aria-label*="삭제"]') ||
                              document.querySelector('.btn_delete');
                if (clearBtn) {
                    clearBtn.click();
                    return true;
                }
                return false;
            })();
            """
            result = self.driver.execute_script(clear_and_search_script)
            if result:
                logger.info("✓ 검색어 삭제 완료")
            else:
                logger.warning("⚠ 검색어 삭제 버튼을 찾을 수 없습니다")
            # self.human_delay(0.5, 1.0)  # 삭제 후 잠시 대기
        except Exception as e:
            logger.error(f"검색어 삭제 실패: {e}")

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

    def search_keyword(self, keyword):
        """키워드 검색 (crawler_galaxy2.py 방식 - JavaScript 기반)"""
        logger.info(f"키워드 검색: {keyword}")
        try:
            # 1. 검색창에 키워드 입력 (JavaScript)
            search_input_script = f"""
            (function() {{
                var searchInput = document.querySelector('#query') || 
                                document.querySelector('input.sch_input') ||
                                document.querySelector('input[type="search"]');
                if (searchInput) {{
                    searchInput.focus();
                    searchInput.click();
                    searchInput.value = '';
                    searchInput.value = '{keyword}';
                    searchInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    return true;
                }}
                return false;
            }})();
            """
            result = self.driver.execute_script(search_input_script)
            if result:
                logger.info(f"✓ 검색어 입력 완료: {keyword}")
            else:
                logger.warning("⚠ 검색창을 찾지 못했습니다.")
                time.sleep(2)
            
            # 2. 검색 버튼 클릭
            search_button_script = """
            (function() {
                var searchButton = document.querySelector('button.sch_btn_search') ||
                                document.querySelector('button.MM_SEARCH_SUBMIT') ||
                                document.querySelector('#sch_w > div > form > button') ||
                                document.querySelector('button[type="submit"]');
                
                if (searchButton) {
                    searchButton.click();
                    return true;
                }
                
                // 버튼을 찾지 못하면 form submit 시도
                var searchInput = document.querySelector('#query') || 
                                document.querySelector('input.sch_input');
                if (searchInput) {
                    var form = searchInput.closest('form');
                    if (form) {
                        form.submit();
                        return true;
                    }
                }
                
                return false;
            })();
            """
            
            button_result = self.driver.execute_script(search_button_script)
            if button_result:
                logger.info("✓ 검색 버튼 클릭 완료")
            else:
                # Enter 키 이벤트 시도
                enter_key_script = """
                (function() {
                    var searchInput = document.querySelector('#query') || 
                                    document.querySelector('input.sch_input');
                    if (searchInput) {
                        var e = new KeyboardEvent('keydown', {
                            key: 'Enter',
                            code: 'Enter',
                            keyCode: 13,
                            bubbles: true
                        });
                        searchInput.dispatchEvent(e);
                        return true;
                    }
                    return false;
                })();
                """
                self.driver.execute_script(enter_key_script)
            
            time.sleep(3)  # 검색 결과 로딩 대기
            
        except Exception as e:
            logger.error(f"검색 실패: {e}", exc_info=True)
            raise

    # 함수 정의 (410번째 줄 전에 추가)
    def search_base_keyword(self, base_keyword):
        """
        기본 검색어를 검색창에 입력하는 함수
        
        Args:
            chrome_dt: ChromeDevTools 인스턴스
            base_keyword: 입력할 기본 검색어
        
        Returns:
            bool: 성공 여부
        """
        try:
            logger.info(f"새 기본 검색어 입력: {base_keyword}")

            clear_and_search_script = f"""
            (function() {{
                // CSS 선택자로 먼저 시도
                var searchInput = document.querySelector('#nx_query') ||
                                document.querySelector('#query') || 
                                document.querySelector('input.sch_input') ||
                                document.querySelector('input[type="search"]') ||
                                document.querySelector('input[type="search"][name="query"]') ||
                                document.querySelector('input[placeholder*="검색"]') ||
                                document.querySelector('input[name="query"]') ||
                                document.querySelector('.search_input');
                
                // CSS 선택자로 찾지 못하면 XPath 절대 경로로 시도
                if (!searchInput) {{
                    try {{
                        var xpathResult = document.evaluate(
                            '//input[@id="nx_query" or @id="query" or contains(@placeholder, "검색") or @type="search"]',
                            document,
                            null,
                            XPathResult.FIRST_ORDERED_NODE_TYPE,
                            null
                        );
                        if (xpathResult.singleNodeValue) {{
                            searchInput = xpathResult.singleNodeValue;
                        }}
                    }} catch (e) {{
                        console.log('XPath 검색 실패: ' + e);
                    }}
                }}
                
                if (searchInput) {{
                    searchInput.focus();
                    searchInput.click();
                    searchInput.value = '';              
                    searchInput.value = '{base_keyword}';
                    searchInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    return true;
                }}
                return false;
            }})();
            """            
            result = self.driver.execute_script(clear_and_search_script)
            
            if result:
                logger.info(f"✓ 기본 검색어 입력 완료: {base_keyword}")
                time.sleep(3)
                return True
            else:
                logger.warning("⚠ 기본 검색어 입력 실패")
                time.sleep(2)
                return False

            button_result = self.driver.execute_script(search_button_script)
            if button_result:
                logger.info("✓ 기본 검색어 검색 버튼 클릭 완료")
            else:
                logger.warning("⚠ 검색 버튼을 찾지 못했습니다. Enter 키 시도...")
                # Enter 키 이벤트 시도
                enter_key_script = """
                (function() {
                    var searchInput = document.querySelector('#nx_query') ||
                                    document.querySelector('#query') || 
                                    document.querySelector('input.sch_input');
                    if (searchInput) {
                        var e = new KeyboardEvent('keydown', {
                            key: 'Enter',
                            code: 'Enter',
                            keyCode: 13,
                            bubbles: true
                        });
                        searchInput.dispatchEvent(e);
                        return true;
                    }
                    return false;
                })();
                """
                self.driver.execute_script(enter_key_script)
            
            time.sleep(3)  # 검색 결과 로딩 대기         
            # SEARCH 까지 확인.    
        except Exception as e:
            logger.error(f"기본 검색어 입력 실패: {e}")
            return False

    def click_by_nvmid(self, nvmid):
        """nvmid로 상품 클릭"""
        logger.info(f"상품 클릭: nvmid={nvmid}")
        
        click_script = create_click_result_script(nvmid)
        result = self.driver.execute_script(click_script)
        
        if result and isinstance(result, dict) and result.get('success'):
            logger.info(f"✓ 상품 클릭 완료: {result.get('nvmid')}")
            # self.human_delay(2, 4)
            return True
        else:
            logger.warning(f"상품을 찾지 못했습니다: {result.get('reason') if result else 'unknown'}")
            return False
    
    def click_purchase_additional_info(self):
        """구매 추가정보 버튼 클릭""" ## 로직 안바뀜.
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

    # NaverCrawler 클래스에 메서드 추가
    def click_by_nvmid_mobile(self, nvmid):
        """nvmid로 상품 클릭 (모바일 터치 이벤트 사용)"""
        logger.info(f"[모바일 클릭] NV MID: {nvmid}")
        
        # 클릭 전 URL 저장
        try:
            url_before_click = self.driver.current_url
            logger.info(f"[모바일 클릭 전] 현재 URL: {url_before_click}")
        except Exception as e:
            logger.warning(f"클릭 전 URL 확인 실패: {e}")
            url_before_click = None
        
        # 페이지 로드 대기
        try:
            logger.info(f"[모바일 클릭] 페이지 로드 대기 중...")
            WebDriverWait(self.driver, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            logger.info(f"[모바일 클릭] 페이지 로드 완료")
        except Exception as e:
            logger.warning(f"[모바일 클릭] 페이지 로드 대기 실패: {e}")
        
        # 추가 대기 (동적 콘텐츠 로드를 위해)
        time.sleep(2)
        
        # 모바일 스크립트 실행하여 좌표 가져오기
        try:
            click_script = create_click_result_script_mobile(nvmid)
            logger.info(f"[모바일 클릭] 스크립트 실행 시작...")
            
            # 페이지가 로드되었는지 확인
            try:
                ready_state = self.driver.execute_script("return document.readyState;")
                logger.info(f"[모바일 클릭] 문서 상태: {ready_state}")
            except Exception as e:
                logger.warning(f"[모바일 클릭] 문서 상태 확인 실패: {e}")
            
            # 요소가 존재하는지 먼저 확인
            try:
                element_count = self.driver.execute_script(
                    "return document.querySelectorAll('li.ds9RptR1 a[aria-labelledby^=\"view_type_guide_\"]').length;"
                )
                logger.info(f"[모바일 클릭] 찾은 요소 개수: {element_count}")
            except Exception as e:
                logger.warning(f"[모바일 클릭] 요소 개수 확인 실패: {e}")
            
            logger.info(f"[모바일 클릭] 스크립트 실행 중...")
            
            # 스크립트 실행 전 간단한 테스트
            try:
                test_result = self.driver.execute_script("return 'test';")
                logger.info(f"[모바일 클릭] JavaScript 실행 테스트: {test_result}")
            except Exception as e:
                logger.error(f"[모바일 클릭] JavaScript 실행 테스트 실패: {e}")
            
            # 스크립트를 단계별로 테스트
            try:
                # 1단계: 요소 찾기 테스트
                find_test = self.driver.execute_script("""
                    var listItems = document.querySelectorAll('li.ds9RptR1 a[aria-labelledby^="view_type_guide_"]');
                    return {
                        count: listItems.length,
                        firstAria: listItems.length > 0 ? listItems[0].getAttribute('aria-labelledby') : null
                    };
                """)
                logger.info(f"[모바일 클릭] 요소 찾기 테스트: {find_test}")
            except Exception as e:
                logger.error(f"[모바일 클릭] 요소 찾기 테스트 실패: {e}")
            
            # 실제 스크립트 실행 (타임아웃 설정)
            try:
                logger.info(f"[모바일 클릭] 전체 스크립트 실행 시작...")
                logger.debug(f"[모바일 클릭] 스크립트 길이: {len(click_script)} 문자")
                
                # 스크립트를 직접 실행해서 반환값 확인
                result = self.driver.execute_script(click_script)
                
                # 결과가 None인 경우 스크립트를 단계별로 실행
                if result is None:
                    logger.warning(f"[모바일 클릭] 스크립트가 None 반환, 단계별 실행 시도...")
                    # 단계 1: 요소 찾기
                    step1 = self.driver.execute_script(f"""
                        var targetNvmid = '{nvmid}';
                        var listItems = document.querySelectorAll('li.ds9RptR1 a[aria-labelledby^="view_type_guide_"]');
                        var aTag = null;
                        for (var i = 0; i < listItems.length; i++) {{
                            var el = listItems[i];
                            var aria = el.getAttribute('aria-labelledby');
                            if (!aria) continue;
                            var nvmid = aria.replace('view_type_guide_', '');
                            if (nvmid === targetNvmid) {{
                                aTag = el;
                                break;
                            }}
                        }}
                        return aTag ? {{found: true, nvmid: targetNvmid}} : {{found: false, nvmid: targetNvmid}};
                    """)
                    logger.info(f"[모바일 클릭] 단계 1 (요소 찾기) 결과: {step1}")
                    
                    if step1 and step1.get('found'):
                        # 단계 2: 좌표 구하기
                        step2 = self.driver.execute_script(f"""
                            var targetNvmid = '{nvmid}';
                            var listItems = document.querySelectorAll('li.ds9RptR1 a[aria-labelledby^="view_type_guide_"]');
                            var aTag = null;
                            var foundNvmid = null;
                            for (var i = 0; i < listItems.length; i++) {{
                                var el = listItems[i];
                                var aria = el.getAttribute('aria-labelledby');
                                if (!aria) continue;
                                var nvmid = aria.replace('view_type_guide_', '');
                                if (nvmid === targetNvmid) {{
                                    aTag = el;
                                    foundNvmid = nvmid;
                                    break;
                                }}
                            }}
                            if (!aTag) return {{success: false, reason: 'not_found'}};
                            
                            // 요소가 보이지 않으면 스크롤
                            var rect = aTag.getBoundingClientRect();
                            var isVisible = rect.width > 0 && rect.height > 0 && 
                                           rect.top >= 0 && rect.left >= 0 &&
                                           rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
                                           rect.right <= (window.innerWidth || document.documentElement.clientWidth);
                            
                            if (!isVisible) {{
                                aTag.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                                var scrollWait = 500;
                                var scrollWaitUntil = Date.now() + scrollWait;
                                while (Date.now() < scrollWaitUntil) {{
                                    // busy wait
                                }}
                                rect = aTag.getBoundingClientRect();
                            }}
                            
                            return {{
                                success: true,
                                nvmid: foundNvmid,
                                coordinates: {{
                                    x: Math.round(rect.left + rect.width / 2),
                                    y: Math.round(rect.top + rect.height / 2),
                                    width: Math.round(rect.width),
                                    height: Math.round(rect.height)
                                }}
                            }};
                        """)
                        logger.info(f"[모바일 클릭] 단계 2 (좌표 구하기) 결과: {step2}")
                        result = step2
                
                logger.info(f"[모바일 클릭] 스크립트 실행 완료")
            except Exception as e:
                logger.error(f"[모바일 클릭] 스크립트 실행 중 예외 발생: {e}", exc_info=True)
                result = None
            
            # 디버깅: result 전체 출력
            logger.info(f"[모바일 클릭] 스크립트 실행 결과: {result}")
            logger.info(f"[모바일 클릭] 결과 타입: {type(result)}")
            
            # None인 경우 추가 디버깅
            if result is None:
                logger.error(f"[모바일 클릭] ⚠️ 스크립트가 None을 반환했습니다!")
                
                # 스크립트를 직접 실행해서 오류 확인
                try:
                    logger.info(f"[모바일 클릭] 스크립트 직접 실행 테스트...")
                    test_script = f"""
                    (function() {{
                        var targetNvmid = '{nvmid}';
                        var listItems = document.querySelectorAll('li.ds9RptR1 a[aria-labelledby^="view_type_guide_"]');
                        return {{
                            targetNvmid: targetNvmid,
                            foundCount: listItems.length,
                            test: 'success'
                        }};
                    }})();
                    """
                    test_result = self.driver.execute_script(test_script)
                    logger.info(f"[모바일 클릭] 간단한 테스트 스크립트 결과: {test_result}")
                except Exception as e:
                    logger.error(f"[모바일 클릭] 간단한 테스트 스크립트 실패: {e}")
                
                # 브라우저 콘솔 오류 확인
                try:
                    console_logs = self.driver.get_log('browser')
                    if console_logs:
                        logger.error(f"[모바일 클릭] 브라우저 콘솔 오류 (최근 10개):")
                        for log in console_logs[-10:]:
                            if log.get('level') in ['SEVERE', 'ERROR']:
                                logger.error(f"  - [{log.get('level')}] {log.get('message')}")
                except Exception as e:
                    logger.warning(f"[모바일 클릭] 브라우저 로그 확인 실패: {e}")
            
        except Exception as e:
            logger.error(f"[모바일 클릭] 스크립트 실행 중 오류 발생: {e}", exc_info=True)
            result = None
        
        if result and isinstance(result, dict):
            # 디버깅 정보 출력
            if 'debug' in result:
                debug_info = result.get('debug', {})
                logger.info(f"[모바일 클릭] 디버깅 정보:")
                logger.info(f"  - 요소가 화면에 보였는지: {debug_info.get('wasVisible', 'N/A')}")
                if 'rectBeforeScroll' in debug_info:
                    rect_info = debug_info.get('rectBeforeScroll', {})
                    logger.info(f"  - 스크롤 전 좌표: left={rect_info.get('left')}, top={rect_info.get('top')}, width={rect_info.get('width')}, height={rect_info.get('height')}")
            
            if result.get('success'):
                coordinates = result.get('coordinates')
                if coordinates:
                    x = coordinates.get('x')
                    y = coordinates.get('y')
                    width = coordinates.get('width')
                    height = coordinates.get('height')
                    logger.info(f"[모바일 클릭] 좌표 가져오기 성공: x={x}, y={y}, width={width}, height={height}")
                    
                    # CDP로 터치 이벤트 발생 (모바일 클릭)
                    try:
                        # 스크롤 방지 및 요소로 스크롤
                        logger.info(f"[모바일 클릭] 요소로 스크롤 및 스크롤 방지...")
                        self.driver.execute_script(f"""
                            var targetNvmid = '{nvmid}';
                            var listItems = document.querySelectorAll('li.ds9RptR1 a[aria-labelledby^="view_type_guide_"]');
                            var aTag = null;
                            for (var i = 0; i < listItems.length; i++) {{
                                var el = listItems[i];
                                var aria = el.getAttribute('aria-labelledby');
                                if (!aria) continue;
                                var nvmid = aria.replace('view_type_guide_', '');
                                if (nvmid === targetNvmid) {{
                                    aTag = el;
                                    break;
                                }}
                            }}
                            if (aTag) {{
                                // 스크롤 방지
                                document.body.style.overflow = 'hidden';
                                // 요소로 스크롤
                                aTag.scrollIntoView({{ behavior: 'instant', block: 'center' }});
                            }}
                        """)
                        time.sleep(0.5)  # 스크롤 완료 대기
                        
                        # 좌표 다시 가져오기 (스크롤 후)
                        updated_result = self.driver.execute_script(f"""
                            var targetNvmid = '{nvmid}';
                            var listItems = document.querySelectorAll('li.ds9RptR1 a[aria-labelledby^="view_type_guide_"]');
                            var aTag = null;
                            for (var i = 0; i < listItems.length; i++) {{
                                var el = listItems[i];
                                var aria = el.getAttribute('aria-labelledby');
                                if (!aria) continue;
                                var nvmid = aria.replace('view_type_guide_', '');
                                if (nvmid === targetNvmid) {{
                                    aTag = el;
                                    break;
                                }}
                            }}
                            if (!aTag) return null;
                            var rect = aTag.getBoundingClientRect();
                            return {{
                                x: Math.round(rect.left + rect.width / 2),
                                y: Math.round(rect.top + rect.height / 2)
                            }};
                        """)
                        
                        if updated_result:
                            x = updated_result.get('x', x)
                            y = updated_result.get('y', y)
                            logger.info(f"[모바일 클릭] 스크롤 후 좌표 업데이트: x={x}, y={y}")
                        
                        # Input.dispatchTouchEvent 사용
                        logger.info(f"[모바일 클릭] 터치 이벤트 발생 시작 (좌표: {x}, {y})...")
                        self.driver.execute_cdp_cmd('Input.dispatchTouchEvent', {
                            'type': 'touchStart',
                            'touchPoints': [{
                                'x': x,
                                'y': y,
                                'radiusX': 2.5,
                                'radiusY': 2.5,
                                'rotationAngle': 10,
                                'force': 0.5,
                                'id': 0
                            }]
                        })
                        
                        time.sleep(1000)  # 짧은 대기
                        
                        self.driver.execute_cdp_cmd('Input.dispatchTouchEvent', {
                            'type': 'touchEnd',
                            'touchPoints': [{
                                'x': x,
                                'y': y,
                                'radiusX': 2.5,
                                'radiusY': 2.5,
                                'rotationAngle': 10,
                                'force': 0.5,
                                'id': 0
                            }]
                        })
                        
                        logger.info(f"[모바일 클릭] ✓ 터치 이벤트 발생 수행 (좌표: {x}, {y})")
                        
                        # 스크롤 방지 해제
                        self.driver.execute_script("document.body.style.overflow = '';")
                        
                        # 네비게이션 대기
                        time.sleep(2)
                        
                        # 클릭 후 URL 확인
                        try:
                            url_after_click = self.driver.current_url
                            url_changed = url_before_click and url_after_click != url_before_click
                            logger.info(f"[모바일 클릭 후] 현재 URL: {url_after_click}")
                            logger.info(f"[모바일 클릭 확인] URL 변경 여부: {url_changed}")
                            
                            if url_changed:
                                logger.info(f"✓ 모바일 클릭 성공 - 링크 변환됨!")
                                return True
                            else:
                                logger.warning(f"⚠ URL이 변경되지 않았습니다")
                                return False
                        except Exception as e:
                            logger.warning(f"클릭 후 URL 확인 실패: {e}")
                            return False
                            
                    except Exception as e:
                        logger.error(f"[모바일 클릭] 터치 이벤트 발생 실패: {e}", exc_info=True)
                        return False
                else:
                    logger.warning(f"[모바일 클릭] 좌표 정보가 없습니다 (success=True이지만 coordinates가 없음)")
                    return False
            else:
                reason = result.get('reason', 'unknown')
                logger.warning(f"[모바일 클릭] 상품을 찾지 못했습니다: {reason}")
                logger.warning(f"[모바일 클릭] 전체 결과: {result}")
                return False
        else:
            logger.error(f"[모바일 클릭] 스크립트 실행 결과가 올바르지 않습니다: {result}")
            return False


def create_click_result_script_mobile(config_nvmid):
    """
    NV MID로 검색 결과를 찾아 모바일 터치 이벤트로 클릭하는 JavaScript 스크립트 생성
    좌표를 가져와서 터치 이벤트로 클릭
    test5.py의 간단한 방식을 사용
    
    Args:
        config_nvmid: 찾을 NV MID 값
    
    Returns:
        str: 실행할 JavaScript 코드
    """
    click_result_script = f"""
    (function() {{
        var targetNvmid = '{config_nvmid}';
        var aTag = null;
        var foundNvmid = null;

        var maxWait = 5000;
        var startTime = Date.now();

        // ⭐ test5.py와 동일한 간단한 방법: 직접 셀렉터 사용
        while (!aTag && (Date.now() - startTime) < maxWait) {{
            var listItems = document.querySelectorAll('li.ds9RptR1 a[aria-labelledby^="view_type_guide_"]');
            
            for (var i = 0; i < listItems.length; i++) {{
                var el = listItems[i];
                var aria = el.getAttribute('aria-labelledby');

                if (!aria) continue;

                var nvmid = aria.replace('view_type_guide_', '');
                
                if (nvmid === targetNvmid) {{
                    aTag = el;
                    foundNvmid = nvmid;
                    break;
                }}
            }}

            if (!aTag) {{
                var waitUntil = Date.now() + 100;
                while (Date.now() < waitUntil) {{
                    // busy wait
                }}
            }}
        }}

        if (!aTag) {{
            return {{
                success: false,
                reason: "nvmid_not_found",
                nvmid: null
            }};
        }}

        // 요소가 보이지 않으면 스크롤
        var rect = aTag.getBoundingClientRect();
        var isVisible = rect.width > 0 && rect.height > 0 && 
                       rect.top >= 0 && rect.left >= 0 &&
                       rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
                       rect.right <= (window.innerWidth || document.documentElement.clientWidth);
        
        if (!isVisible) {{
            aTag.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
            var scrollWait = 500;
            var scrollWaitUntil = Date.now() + scrollWait;
            while (Date.now() < scrollWaitUntil) {{
                // busy wait
            }}
            // 스크롤 후 좌표 다시 가져오기
            rect = aTag.getBoundingClientRect();
        }}

        // 요소가 클릭 가능한지 확인
        var computedStyle = window.getComputedStyle(aTag);
        var isClickable = computedStyle.display !== 'none' && 
                         computedStyle.visibility !== 'hidden' &&
                         computedStyle.pointerEvents !== 'none';
        
        if (!isClickable) {{
            return {{ 
                success: false, 
                nvmid: foundNvmid, 
                reason: 'not_clickable'
            }};
        }}

        // 좌표 반환 (중심점 계산)
        var centerX = rect.left + (rect.width / 2);
        var centerY = rect.top + (rect.height / 2);

        return {{
            success: true,
            nvmid: foundNvmid,
            coordinates: {{
                x: Math.round(centerX),
                y: Math.round(centerY),
                width: Math.round(rect.width),
                height: Math.round(rect.height)
            }}
        }};
    }})();
    """
    
    return click_result_script


def cleanup_all_chrome_sessions():
    """
    모든 Chrome 세션 및 쿠키 정리
    - 실행 중인 Chrome 프로세스 종료
    - chrome_data_* 디렉토리 삭제
    - 임시 디렉토리 정리
    """
    logger.info("=" * 50)
    logger.info("모든 Chrome 세션 및 쿠키 정리 시작")
    logger.info("=" * 50)
    
    try:
        # 1. 실행 중인 Chrome 프로세스 종료
        logger.info("[세션 정리] Chrome 프로세스 종료 중...")
        if platform.system() == 'Windows':
            try:
                # Windows에서 Chrome 프로세스 종료
                subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'], 
                             capture_output=True, timeout=10)
                subprocess.run(['taskkill', '/F', '/IM', 'chromedriver.exe'], 
                             capture_output=True, timeout=10)
                logger.info("✓ Chrome 프로세스 종료 완료")
            except Exception as e:
                logger.warning(f"Chrome 프로세스 종료 중 오류: {e}")
        else:
            # Linux/Mac에서 Chrome 프로세스 종료
            try:
                subprocess.run(['pkill', '-f', 'chrome'], 
                             capture_output=True, timeout=10)
                subprocess.run(['pkill', '-f', 'chromedriver'], 
                             capture_output=True, timeout=10)
                logger.info("✓ Chrome 프로세스 종료 완료")
            except Exception as e:
                logger.warning(f"Chrome 프로세스 종료 중 오류: {e}")
        
        # 프로세스 종료 대기
        time.sleep(2)
        
        # 2. chrome_data_* 디렉토리 삭제
        logger.info("[세션 정리] chrome_data_* 디렉토리 정리 중...")
        current_dir = os.getcwd()
        deleted_count = 0
        
        try:
            for item in os.listdir(current_dir):
                item_path = os.path.join(current_dir, item)
                
                # chrome_data_로 시작하는 디렉토리 찾기
                if os.path.isdir(item_path) and item.startswith('chrome_data_'):
                    try:
                        # 잠금 파일 먼저 삭제 시도
                        lock_files = [
                            os.path.join(item_path, 'SingletonLock'),
                            os.path.join(item_path, 'Default', 'LockFile')
                        ]
                        for lock_file in lock_files:
                            if os.path.exists(lock_file):
                                try:
                                    os.remove(lock_file)
                                except:
                                    pass
                        
                        # 디렉토리 삭제
                        shutil.rmtree(item_path, ignore_errors=True)
                        deleted_count += 1
                        logger.info(f"✓ 디렉토리 삭제: {item}")
                    except Exception as e:
                        logger.warning(f"디렉토리 삭제 실패 ({item}): {e}")
            
            if deleted_count > 0:
                logger.info(f"✓ 총 {deleted_count}개 chrome_data_* 디렉토리 삭제 완료")
            else:
                logger.info("삭제할 chrome_data_* 디렉토리가 없습니다")
        except Exception as e:
            logger.warning(f"디렉토리 정리 중 오류: {e}")
        
        # 3. 임시 디렉토리 정리 (tempfile로 생성된 것들)
        logger.info("[세션 정리] 임시 디렉토리 정리 중...")
        temp_dir = tempfile.gettempdir()
        
        try:
            temp_deleted = 0
            for item in os.listdir(temp_dir):
                item_path = os.path.join(temp_dir, item)
                
                # chrome_data_로 시작하는 임시 디렉토리 찾기
                if os.path.isdir(item_path) and item.startswith('chrome_data_'):
                    try:
                        shutil.rmtree(item_path, ignore_errors=True)
                        temp_deleted += 1
                    except:
                        pass
            
            if temp_deleted > 0:
                logger.info(f"✓ 총 {temp_deleted}개 임시 디렉토리 삭제 완료")
        except Exception as e:
            logger.warning(f"임시 디렉토리 정리 중 오류: {e}")
        
        logger.info("=" * 50)
        logger.info("✓ 모든 Chrome 세션 및 쿠키 정리 완료")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"세션 정리 중 오류: {e}", exc_info=True)


def test_single_iteration(row_data, iteration_id, headless=False):
    """
    단일 반복 테스트 함수
    
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
        logger.info(f"[반복 {iteration_id}] 크롤러 생성 시작")
        logger.info(f"[반복 {iteration_id}] ========================================")
        
        # 🔑 모바일 모드 전환 (nv_mid 클릭 전에 추가)

        # 크롤러 생성
        try:
            crawler = NaverCrawler(instance_id=iteration_id, headless=headless)
            logger.info(f"[반복 {iteration_id}] ✓ 크롤러 생성 완료")
        except Exception as e:
            logger.error(f"[반복 {iteration_id}] ✗ 크롤러 생성 실패: {e}", exc_info=True)
            return False

        logger.info(f"[반복 {iteration_id}] 모바일 모드로 전환 중...")
        if crawler.enable_mobile_mode():
            logger.info(f"[반복 {iteration_id}] ✓ 모바일 모드 전환 완료")
            logger.info(f"[반복 {iteration_id}] ✓ 모바일 버전 페이지 로드 완료")
        else:
            logger.warning(f"[반복 {iteration_id}] ⚠ 모바일 모드 전환 실패, 계속 진행...")                
        # 네이버 접속
        crawler.navigate_to_naver()

        # 메인 키워드 검색
        if 'main_keyword' in row_data and pd.notna(row_data['main_keyword']):
            crawler.search_keyword(row_data['main_keyword'])
            time.sleep(4)

        # 새 검색어로 검색
        # 그냥 네이버로 네비게이션 검색 전과 후의 id 는 계속 달라집니다. -- 바뀔 가능성이 있음. 
        crawler.navigate_to_naver()
        if crawler.enable_mobile_mode():
            logger.info(f"[반복 {iteration_id}] ✓ 모바일 모드 전환 완료")
            logger.info(f"[반복 {iteration_id}] ✓ 모바일 버전 페이지 로드 완료")
        else:
            logger.warning(f"[반복 {iteration_id}] ⚠ 모바일 모드 전환 실패, 계속 진행...")                
        time.sleep(3)
        if 'base_search_keyword' in row_data and pd.notna(row_data['base_search_keyword']):
            crawler.search_keyword(row_data['base_search_keyword'])
            time.sleep(4)
        # pdb.set_trace()
        # nvmid로 상품 클릭
        if 'nv_mid' in row_data and pd.notna(row_data['nv_mid']):
            crawler.click_by_nvmid(str(row_data['nv_mid']))
            # crawler.click_by_nvmid_mobile(str(row_data['nv_mid']))
        time.sleep(3)

        # 구매 추가정보 버튼 클릭
        crawler.click_purchase_additional_info()
        time.sleep(4)
        
        logger.info(f"[반복 {iteration_id}] 크롤링 완료")
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
    logger.info("일반 셀레니움 크롤링 테스트 시작")
    logger.info("=" * 50)
    # change_ip()
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
    finally:
        # ⭐ 모든 쓰레드가 끝난 후 Chrome 세션 및 쿠키 정리
        cleanup_all_chrome_sessions()


if __name__ == '__main__':
    main()

