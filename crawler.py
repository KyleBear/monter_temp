import time
import logging
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from config import Config
from session_middleware import SessionMiddleware

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class NaverStoreCrawler:
    def __init__(self):
        self.config = Config()
        self.driver = None
        self.session_middleware = None
        self.setup_driver()
    
    def setup_driver(self):
        """크롬 드라이버 설정"""
        chrome_options = Options()
        
        # USB 연결된 휴대폰 Chrome 사용 여부 확인
        use_remote_device = hasattr(self.config, 'USE_REMOTE_DEVICE') and self.config.USE_REMOTE_DEVICE
        
        if use_remote_device:
            # 원격 디바이스 모드: 최소한의 옵션만 사용 (크래시 방지)
            # debuggerAddress만 설정하고 다른 옵션은 추가하지 않음
            chrome_options.add_experimental_option("debuggerAddress", f"127.0.0.1:{self.config.REMOTE_DEBUGGING_PORT}")
            logger.info(f"USB 연결된 휴대폰 Chrome에 연결: localhost:{self.config.REMOTE_DEBUGGING_PORT}")
            logger.info("주의: 휴대폰에서 Chrome이 실행 중이어야 하며, USB 디버깅이 활성화되어 있어야 합니다.")
            logger.info("원격 디바이스 모드: 최소한의 옵션만 사용 (안정성 향상)")
        else:
            # 기존 PC Chrome 설정
            # 시크릿 모드 (Incognito) 활성화
            chrome_options.add_argument('--incognito')
            
            # 모바일 뷰포트 설정
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36')
            chrome_options.add_argument('--window-size=375,667')
            
            # 세션 및 캐시 삭제를 위한 옵션 (원격 디바이스가 아닐 때만)
            chrome_options.add_argument('--disable-application-cache')
            chrome_options.add_argument('--disable-cache')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
        
        # 헤드리스 모드 (필요시 주석 해제)
        # chrome_options.add_argument('--headless')
        
        # ChromeDriver 경로 설정
        import platform
        system = platform.system()
        driver_names = ['chromedriver.exe', 'chromedriver'] if system == 'Windows' else ['chromedriver']
        driver_path = None
        
        try:
            # win64 버전을 강제로 선택하기 위한 커스텀 ChromeDriverManager
            class Win64ChromeDriverManager(ChromeDriverManager):
                def get_os_type(self):
                    os_type = super().get_os_type()
                    # ChromeDriverManager의 get_os_type()이 win32를 반환하므로 win64로 변경
                    if "win" in os_type.lower() or os_type == "win32":
                        return "win64"
                    return os_type
            
            # Chrome 138 버전 명시적으로 지정 (휴대폰 Chrome 버전)
            logger.info("Chrome 138 버전의 ChromeDriver를 다운로드합니다...")
            manager = Win64ChromeDriverManager(driver_version="138")
            manager_path = manager.install()
            logger.debug(f"ChromeDriverManager 반환 경로: {manager_path}")
            logger.info("win64 버전의 ChromeDriver를 사용합니다.")
            
            search_dir = None
            
            # 반환된 경로가 파일인지 확인
            if os.path.isfile(manager_path):
                # 직접 파일 경로인 경우
                if any(manager_path.endswith(name) for name in driver_names):
                    # Windows에서 win32 경로는 사용하지 않음
                    if system == 'Windows' and 'win32' in manager_path:
                        logger.warning(f"win32 버전 발견 (사용 안 함): {manager_path}")
                        logger.warning("win64 버전을 찾는 중...")
                        search_dir = os.path.dirname(manager_path)
                        driver_path = None
                    else:
                        driver_path = manager_path
                        logger.info(f"ChromeDriver 찾음 (직접 파일): {driver_path}")
                else:
                    # 파일이지만 chromedriver가 아닌 경우 (예: zip 파일)
                    search_dir = os.path.dirname(manager_path)
            elif os.path.isdir(manager_path):
                # 디렉토리인 경우 하위 디렉토리에서 재귀적으로 검색
                search_dir = manager_path
            else:
                # 경로가 존재하지 않는 경우
                search_dir = os.path.dirname(manager_path) if manager_path else None
            
            # 디렉토리에서 chromedriver 찾기
            if search_dir and os.path.exists(search_dir):
                # Windows 64비트 시스템에서는 win64 버전을 우선적으로 찾음
                if system == 'Windows':
                    # win64 경로 우선 검색
                    win64_paths = []
                    win32_paths = []
                    other_paths = []
                    
                    for root, dirs, files in os.walk(search_dir):
                        for file in files:
                            if file in driver_names:
                                file_path = os.path.join(root, file)
                                if os.path.isfile(file_path):
                                    # THIRD_PARTY_NOTICES 같은 파일 제외 (경로와 파일명 모두 확인)
                                    file_path_lower = file_path.lower()
                                    if ('third_party' not in file_path_lower and 
                                        'notices' not in file_path_lower and
                                        not file_path.endswith('.txt') and
                                        not file_path.endswith('.md') and
                                        not file_path.endswith('.LICENSE')):
                                        # 실제 실행 파일인지 확인 (Windows에서는 .exe 확장자 확인)
                                        if system == 'Windows':
                                            if file_path.endswith('.exe'):
                                                if 'win64' in file_path:
                                                    win64_paths.append(file_path)
                                                elif 'win32' in file_path:
                                                    win32_paths.append(file_path)
                                                else:
                                                    other_paths.append(file_path)
                                        else:
                                            # Linux/macOS: 실행 권한 확인
                                            if os.access(file_path, os.X_OK):
                                                if 'win64' in file_path:
                                                    win64_paths.append(file_path)
                                                elif 'win32' in file_path:
                                                    win32_paths.append(file_path)
                                                else:
                                                    other_paths.append(file_path)
                    
                    # win64 버전 우선 선택
                    if win64_paths:
                        driver_path = win64_paths[0]
                        logger.info(f"ChromeDriver 찾음 (win64): {driver_path}")
                    elif other_paths:
                        driver_path = other_paths[0]
                        logger.info(f"ChromeDriver 찾음: {driver_path}")
                    elif win32_paths:
                        logger.warning(f"win64 버전을 찾을 수 없어 win32 버전 발견: {win32_paths[0]}")
                        logger.warning("64비트 시스템에서 32비트 ChromeDriver는 '올바른 Win32 응용 프로그램이 아닙니다' 오류가 발생할 수 있습니다.")
                        logger.warning("win64 버전의 ChromeDriver를 다운로드하세요.")
                        # win32 버전은 사용하지 않음 (오류 발생)
                        driver_path = None
                else:
                    # Linux/macOS: 깊은 경로까지 검색
                    for root, dirs, files in os.walk(search_dir):
                        for file in files:
                            if file in driver_names:
                                file_path = os.path.join(root, file)
                                # 파일 존재 확인
                                if os.path.isfile(file_path):
                                    # 실행 권한 확인
                                    if os.access(file_path, os.X_OK):
                                        # THIRD_PARTY_NOTICES 같은 파일 제외
                                        if 'THIRD_PARTY' not in file_path and 'NOTICES' not in file_path:
                                            driver_path = file_path
                                            logger.info(f"ChromeDriver 찾음: {driver_path}")
                                            break
                        if driver_path:
                            break
            
            # 여전히 찾지 못한 경우, manager_path 자체가 파일인지 다시 확인
            if not driver_path and os.path.isfile(manager_path):
                # Windows에서 win32 경로는 사용하지 않음
                if system == 'Windows':
                    if manager_path.endswith('.exe') and 'win32' not in manager_path:
                        driver_path = manager_path
                        logger.info(f"ChromeDriver 찾음 (직접 경로): {driver_path}")
                    elif 'win32' in manager_path:
                        logger.warning(f"win32 버전 발견 (사용 안 함): {manager_path}")
                        logger.warning("win64 버전을 찾을 수 없습니다. fix_chromedriver.py를 실행하세요.")
                elif system != 'Windows' and not manager_path.endswith('.exe'):
                    driver_path = manager_path
                    logger.info(f"ChromeDriver 찾음 (직접 경로): {driver_path}")
            
            # Service 설정
            if driver_path:
                # Windows에서 win32 경로는 절대 사용하지 않음
                if system == 'Windows' and 'win32' in driver_path:
                    logger.error(f"win32 버전이 선택되었습니다 (사용 불가): {driver_path}")
                    logger.error("win64 버전의 ChromeDriver가 필요합니다.")
                    logger.error("다음 명령을 실행하세요: python fix_chromedriver.py --remove-win32 138")
                    raise RuntimeError("win32 ChromeDriver는 64비트 시스템에서 사용할 수 없습니다. win64 버전을 다운로드하세요.")
                
                # 파일 존재 및 win64 확인
                if not os.path.exists(driver_path):
                    logger.error(f"ChromeDriver 파일이 존재하지 않습니다: {driver_path}")
                    raise FileNotFoundError(f"ChromeDriver 파일을 찾을 수 없습니다: {driver_path}")
                
                # win64 경로 확인 (Windows만)
                if system == 'Windows':
                    if 'win64' not in driver_path and 'win32' not in driver_path:
                        logger.warning(f"경로에 win64/win32가 없습니다: {driver_path}")
                    elif 'win32' in driver_path:
                        logger.error(f"win32 경로가 감지되었습니다: {driver_path}")
                        raise RuntimeError("win32 ChromeDriver는 사용할 수 없습니다. win64 버전을 다운로드하세요.")
                
                service = Service(driver_path)
                logger.info(f"ChromeDriver Service 생성 (win64): {driver_path}")
            else:
                # 찾지 못한 경우
                if system == 'Windows':
                    logger.warning("win64 버전의 ChromeDriver를 찾을 수 없습니다.")
                    logger.info("Win64ChromeDriverManager를 사용하여 win64 버전을 다운로드합니다...")
                    try:
                        # Win64ChromeDriverManager로 다시 시도 (Chrome 138 버전 명시)
                        win64_manager = Win64ChromeDriverManager(driver_version="138")
                        win64_driver_path = win64_manager.install()
                        
                        # win64 경로 확인
                        if 'win64' in win64_driver_path or ('win32' not in win64_driver_path and os.path.isfile(win64_driver_path)):
                            driver_path = win64_driver_path
                            logger.info(f"win64 ChromeDriver 다운로드 완료: {driver_path}")
                            service = Service(driver_path)
                        else:
                            logger.error(f"다운로드된 ChromeDriver가 win32 버전입니다: {win64_driver_path}")
                            raise RuntimeError("win64 ChromeDriver 다운로드 실패. fix_chromedriver.py를 실행하세요.")
                    except Exception as e2:
                        logger.error(f"win64 ChromeDriver 다운로드 실패: {e2}")
                        logger.error("다음 명령을 실행하여 win64 버전을 다운로드하세요:")
                        logger.error("  python fix_chromedriver.py --remove-win32 138")
                        raise RuntimeError("win64 ChromeDriver를 찾을 수 없습니다. fix_chromedriver.py를 실행하여 다운로드하세요.")
                else:
                    # Linux/macOS: 기본 경로 사용
                    logger.warning("ChromeDriver 실행 파일을 찾을 수 없어 webdriver-manager 기본 경로 사용")
                    logger.warning("이 경우 webdriver-manager가 자동으로 ChromeDriver를 다운로드하거나 찾을 것입니다.")
                    service = Service()
                    
        except Exception as e:
            logger.error(f"ChromeDriverManager 오류: {e}")
            if system == 'Windows':
                logger.warning("Win64ChromeDriverManager로 재시도합니다...")
                try:
                    # Win64ChromeDriverManager로 재시도 (Chrome 138 버전 명시)
                    win64_manager = Win64ChromeDriverManager(driver_version="138")
                    win64_driver_path = win64_manager.install()
                    
                    # win64 경로 확인
                    if 'win64' in win64_driver_path or ('win32' not in win64_driver_path and os.path.isfile(win64_driver_path)):
                        logger.info(f"win64 ChromeDriver 다운로드 완료: {win64_driver_path}")
                        service = Service(win64_driver_path)
                    else:
                        logger.error(f"다운로드된 ChromeDriver가 win32 버전입니다: {win64_driver_path}")
                        raise RuntimeError("win64 ChromeDriver 다운로드 실패. fix_chromedriver.py를 실행하세요.")
                except Exception as e2:
                    logger.error(f"win64 ChromeDriver 다운로드 실패: {e2}")
                    logger.error("Windows에서는 win64 버전의 ChromeDriver가 필요합니다.")
                    logger.error("다음 명령을 실행하여 win64 버전을 다운로드하세요:")
                    logger.error("  python fix_chromedriver.py --remove-win32 138")
                    raise RuntimeError(f"ChromeDriver 설정 실패: {e}. win64 버전을 다운로드하세요.")
            else:
                logger.warning("webdriver-manager가 자동으로 ChromeDriver를 처리할 것입니다.")
                service = Service()
        
        try:
            logger.info("Chrome 드라이버 생성 시도 중...")
            if use_remote_device:
                logger.info("원격 디바이스 모드: 이미 실행 중인 Chrome에 연결합니다.")
                logger.info("주의: ChromeDriver는 연결 도구로만 사용되며, 새로운 Chrome 인스턴스를 시작하지 않습니다.")
            
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.implicitly_wait(self.config.IMPLICIT_WAIT)
            logger.info("Chrome 드라이버 생성 성공")
            
            # 드라이버 연결 확인
            try:
                self.driver.current_url
                logger.info("Chrome 드라이버 연결 확인 완료")
            except Exception as conn_e:
                logger.warning(f"Chrome 드라이버 연결 확인 중 경고: {conn_e}")
                
        except OSError as e:
            error_msg = str(e)
            if "올바른 Win32 응용 프로그램이 아닙니다" in error_msg or "win32" in error_msg.lower():
                logger.error("=" * 60)
                logger.error("ChromeDriver 아키텍처 오류")
                logger.error("=" * 60)
                logger.error("win32 버전의 ChromeDriver가 사용되었습니다.")
                logger.error("64비트 시스템에서는 win64 버전이 필요합니다.")
                logger.error("해결 방법:")
                logger.error("  python fix_chromedriver.py --remove-win32 138")
                logger.error("=" * 60)
                raise RuntimeError("win32 ChromeDriver는 사용할 수 없습니다. win64 버전을 다운로드하세요.") from e
            elif "unreserved backtrace" in error_msg.lower() or "backtrace" in error_msg.lower():
                logger.error("=" * 60)
                logger.error("ChromeDriver 크래시 오류 (unreserved backtrace)")
                logger.error("=" * 60)
                logger.error("가능한 원인:")
                logger.error("1. ChromeDriver와 Chrome 브라우저 버전 불일치")
                logger.error("2. 손상된 ChromeDriver 파일")
                logger.error("3. 메모리 부족 또는 시스템 리소스 문제")
                logger.error("4. 원격 디바이스 연결 문제 (포트 포워딩 실패)")
                logger.error("5. 원격 디바이스 모드에서 충돌하는 Chrome 옵션")
                logger.error("해결 방법:")
                logger.error("1. ChromeDriver 재설치: python fix_chromedriver.py --remove-win32 138")
                logger.error("2. 휴대폰 Chrome 버전 확인 (현재: 138.0.7204.179)")
                logger.error("3. ADB 포트 포워딩 확인: adb forward --list")
                logger.error("4. 휴대폰에서 Chrome 재시작")
                logger.error("5. 원격 디바이스 모드에서는 Chrome 옵션을 최소화했습니다.")
                logger.error("=" * 60)
                raise RuntimeError("ChromeDriver 크래시 발생. 위의 해결 방법을 시도하세요.") from e
            else:
                raise
        except Exception as e:
            logger.error(f"Chrome 드라이버 생성 실패: {e}")
            logger.error("=" * 60)
            logger.error("문제 해결 방법:")
            logger.error("1. Chrome 브라우저가 설치되어 있는지 확인")
            logger.error("2. ChromeDriver가 올바른 버전인지 확인 (Chrome 버전과 일치해야 함)")
            logger.error("3. ChromeDriver 실행 파일에 접근 권한이 있는지 확인")
            if use_remote_device:
                logger.error("4. 원격 디바이스 모드:")
                logger.error("   - 휴대폰에서 Chrome이 실행 중인지 확인")
                logger.error("   - ADB 포트 포워딩이 설정되어 있는지 확인")
                logger.error("   - 포트가 올바르게 설정되어 있는지 확인")
                logger.error("   - ChromeDriver와 휴대폰 Chrome 버전이 호환되는지 확인")
            logger.error("=" * 60)
            raise
        
        # 세션 미들웨어 초기화
        self.session_middleware = SessionMiddleware(self.driver)
        logger.info("크롬 드라이버 설정 완료")
    
    def navigate_to_naver(self):
        """m.naver.com으로 이동"""
        try:
            self.driver.get(self.config.NAVER_MOBILE_URL)
            time.sleep(self.config.ACTION_DELAY)
            logger.info("네이버 모바일 페이지 접속 완료")
        except Exception as e:
            logger.error(f"네이버 접속 중 오류: {e}")
            raise
    
    def search_main_keyword(self, keyword):
        """메인 키워드 검색"""
        try:
            # 검색창 찾기 (여러 선택자 시도) - element_to_be_clickable 사용
            # 먼저 가짜 검색창을 클릭하여 실제 검색창을 활성화
            fake_search = None
            try:
                fake_search = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "#MM_SEARCH_FAKE"))
                )
                fake_search.click()
                time.sleep(1)
                logger.debug("가짜 검색창 클릭하여 실제 검색창 활성화")
            except:
                pass  # 가짜 검색창이 없으면 건너뜀
            
            # 실제 검색창 찾기
            search_selectors = [
                "#query",  # 실제 검색창 ID (최우선)
                "input.sch_input[data-focus='focus']",  # 포커스된 검색창
                "input.sch_input",  # 네이버 모바일 검색창 클래스
                ".sch_input",  # 네이버 모바일 검색창 클래스
                "input[type='search'][name='query']",  # name과 type 조합
                "input[type='search']",
                "input[placeholder*='검색']",
                "input[name='query']",
                ".search_input"
            ]
            
            search_input = None
            for idx, selector in enumerate(search_selectors):
                try:
                    # 첫 번째 선택자만 긴 대기 시간 사용, 나머지는 짧은 시간 사용
                    wait_time = self.config.EXPLICIT_WAIT if idx == 0 else 2
                    # visibility_of_element_located로 먼저 찾기
                    search_input = WebDriverWait(self.driver, wait_time).until(
                        EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    # 클릭 가능할 때까지 추가 대기 (짧은 시간)
                    WebDriverWait(self.driver, 2).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    break
                except:
                    continue
            
            if not search_input:
                # XPath로 시도
                try:
                    search_input = WebDriverWait(self.driver, self.config.EXPLICIT_WAIT).until(
                        EC.visibility_of_element_located((By.XPATH, "//input[contains(@placeholder, '검색') or @type='search']"))
                    )
                    WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, "//input[contains(@placeholder, '검색') or @type='search']"))
                    )
                except:
                    raise TimeoutException("검색창을 찾을 수 없습니다")
            
            # 요소가 보이도록 스크롤
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", search_input)
            time.sleep(1)
            
            # JavaScript로 직접 입력 시도 (더 안정적)
            try:
                self.driver.execute_script("arguments[0].value = '';", search_input)
                self.driver.execute_script("arguments[0].value = arguments[1];", search_input, keyword)
                # input 이벤트 발생
                self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", search_input)
                time.sleep(1)
                # 엔터 키 이벤트
                search_input.send_keys("\n")
                logger.info(f"메인 키워드 검색 완료 (JavaScript): {keyword}")
            except:
                # JavaScript 실패 시 일반 방법 시도
                try:
                    search_input.clear()
                    search_input.send_keys(keyword)
                    time.sleep(self.config.ACTION_DELAY)
                    search_input.send_keys("\n")
                    logger.info(f"메인 키워드 검색 완료 (일반): {keyword}")
                except Exception as e2:
                    logger.error(f"검색 입력 실패: {e2}")
                    raise
            
            time.sleep(self.config.SEARCH_WAIT)
        except TimeoutException:
            logger.error("검색창을 찾을 수 없습니다")
            raise
        except Exception as e:
            logger.error(f"검색 중 오류: {e}")
            raise
    
    def clear_search_and_input_new(self, new_keyword):
        """검색어 지우고 새 검색어 입력"""
        try:
            # 검색창에서 x 버튼 찾기 (검색어 삭제)
            clear_selectors = [
                "button[aria-label*='삭제']",
                ".btn_delete",
                ".search_delete",
                "button.delete",
                ".ico_delete"
            ]
            
            clear_button = None
            for selector in clear_selectors:
                try:
                    clear_button = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    break
                except:
                    continue
            
            if not clear_button:
                # XPath로 시도
                try:
                    clear_button = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[contains(@aria-label, '삭제') or contains(@class, 'delete')]"))
                    )
                except:
                    pass
            
            if clear_button:
                clear_button.click()
                time.sleep(1)
                logger.debug("검색어 삭제 버튼 클릭 완료")
            
            # 새 검색어 입력
            # 실제 검색창 찾기 (가짜 검색창 클릭 불필요, 이미 검색 페이지에 있음)
            search_selectors = [
                "#query",  # 실제 검색창 ID (최우선)
                "input.sch_input[data-focus='focus']",  # 포커스된 검색창
                "input.sch_input",  # 네이버 모바일 검색창 클래스
                ".sch_input",  # 네이버 모바일 검색창 클래스
                "input[type='search'][name='query']",  # name과 type 조합
                "input[type='search']",
                "input[placeholder*='검색']",
                "input[name='query']",
                ".search_input"
            ]
            
            search_input = None
            for idx, selector in enumerate(search_selectors):
                try:
                    # 첫 번째 선택자만 긴 대기 시간 사용, 나머지는 짧은 시간 사용
                    wait_time = self.config.EXPLICIT_WAIT if idx == 0 else 2
                    # visibility_of_element_located로 먼저 찾기
                    search_input = WebDriverWait(self.driver, wait_time).until(
                        EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    # 클릭 가능할 때까지 추가 대기 (짧은 시간)
                    WebDriverWait(self.driver, 2).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    break
                except:
                    continue
            
            if not search_input:
                try:
                    search_input = WebDriverWait(self.driver, self.config.EXPLICIT_WAIT).until(
                        EC.visibility_of_element_located((By.XPATH, "//input[contains(@placeholder, '검색') or @type='search']"))
                    )
                    WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, "//input[contains(@placeholder, '검색') or @type='search']"))
                    )
                except:
                    raise TimeoutException("검색창을 찾을 수 없습니다")
            
            # 요소가 보이도록 스크롤
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", search_input)
            time.sleep(1)
            
            # JavaScript로 직접 입력 시도 (더 안정적)
            try:
                self.driver.execute_script("arguments[0].value = '';", search_input)
                self.driver.execute_script("arguments[0].value = arguments[1];", search_input, new_keyword)
                # input 이벤트 발생
                self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", search_input)
                time.sleep(1)
                # 엔터 키 이벤트
                search_input.send_keys("\n")
                logger.info(f"새 검색어 입력 완료 (JavaScript): {new_keyword}")
            except:
                # JavaScript 실패 시 일반 방법 시도
                try:
                    search_input.clear()
                    search_input.send_keys(new_keyword)
                    time.sleep(self.config.ACTION_DELAY)
                    search_input.send_keys("\n")
                    logger.info(f"새 검색어 입력 완료 (일반): {new_keyword}")
                except Exception as e2:
                    logger.error(f"검색어 입력 실패: {e2}")
                    raise
            
            time.sleep(3)
        except TimeoutException:
            logger.warning("검색어 삭제 버튼을 찾을 수 없습니다. 계속 진행합니다.")
            # 검색어 삭제 실패해도 새 검색어 입력 시도
            try:
                search_input = WebDriverWait(self.driver, self.config.EXPLICIT_WAIT).until(
                    EC.visibility_of_element_located((By.XPATH, "//input[contains(@placeholder, '검색') or @type='search']"))
                )
                WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, "//input[contains(@placeholder, '검색') or @type='search']"))
                )
                
                # 요소가 보이도록 스크롤
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", search_input)
                time.sleep(1)
                
                # JavaScript로 직접 입력 시도
                try:
                    self.driver.execute_script("arguments[0].value = '';", search_input)
                    self.driver.execute_script("arguments[0].value = arguments[1];", search_input, new_keyword)
                    self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", search_input)
                    time.sleep(1)
                    search_input.send_keys("\n")
                    logger.info(f"새 검색어 입력 완료 (JavaScript): {new_keyword}")
                except:
                    search_input.clear()
                    search_input.send_keys(new_keyword)
                    time.sleep(self.config.ACTION_DELAY)
                    search_input.send_keys("\n")
                    logger.info(f"새 검색어 입력 완료 (일반): {new_keyword}")
                
                time.sleep(self.config.SEARCH_WAIT)
            except Exception as e:
                logger.error(f"검색어 입력 중 오류: {e}")
                raise
        except Exception as e:
            logger.error(f"검색어 변경 중 오류: {e}")
            raise
    
    def click_purchase_additional_info(self):
        """제품 하단에 구매 추가정보 버튼 클릭"""
        try:
            # 우선순위 1: data-shp-area-id="info" 속성으로 찾기
            button = None
            try:
                button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "a[data-shp-area-id='info']"))
                )
                logger.info("구매 추가정보 버튼 찾음 (data-shp-area-id='info')")
            except TimeoutException:
                logger.debug("data-shp-area-id='info'로 버튼을 찾지 못함, 텍스트로 시도")
            
            # 우선순위 2: 텍스트 "구매 추가정보"로 찾기
            if not button:
                try:
                    button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), '구매 추가정보')]"))
                    )
                    logger.info("구매 추가정보 버튼 찾음 (텍스트)")
                except TimeoutException:
                    logger.debug("텍스트로도 버튼을 찾지 못함, 추가 선택자 시도")
            
            # 우선순위 3: 추가 선택자 시도
            if not button:
                selectors = [
                    ("XPATH", "//*[contains(text(), '구매 추가정보')]"),
                    ("XPATH", "//*[contains(text(), '구매추가정보')]"),
                    ("XPATH", "//a[contains(@href, 'additional')]"),
                ]
                
                for selector_type, selector in selectors:
                    try:
                        if selector_type == "XPATH":
                            button = WebDriverWait(self.driver, 3).until(
                                EC.presence_of_element_located((By.XPATH, selector))
                            )
                        if button and button.is_displayed():
                            logger.info(f"구매 추가정보 버튼 찾음 ({selector_type}={selector})")
                            break
                    except:
                        continue
            
            # 버튼을 찾지 못한 경우 페이지 하단으로 스크롤
            if not button:
                logger.info("버튼을 찾지 못해 페이지 하단으로 스크롤 시도")
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                
                # 스크롤 후 다시 시도
                try:
                    button = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "a[data-shp-area-id='info']"))
                    )
                    logger.info("스크롤 후 버튼 찾음 (data-shp-area-id='info')")
                except:
                    try:
                        button = WebDriverWait(self.driver, 3).until(
                            EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), '구매 추가정보')]"))
                        )
                        logger.info("스크롤 후 버튼 찾음 (텍스트)")
                    except:
                        pass
            
            if button and button.is_displayed():
                # 스크롤하여 버튼이 보이도록
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", button)
                time.sleep(1)
                
                # JavaScript로 클릭 시도 (더 안정적)
                try:
                    self.driver.execute_script("arguments[0].click();", button)
                    logger.info("구매 추가정보 버튼 클릭 완료 (JavaScript)")
                except:
                    button.click()
                    logger.info("구매 추가정보 버튼 클릭 완료 (일반)")
                
                time.sleep(self.config.ACTION_DELAY)
            else:
                logger.warning("구매 추가정보 버튼을 찾을 수 없습니다")
        except TimeoutException:
            logger.warning("구매 추가정보 버튼을 찾을 수 없습니다 (타임아웃)")
        except Exception as e:
            logger.error(f"구매 추가정보 버튼 클릭 중 오류: {e}")
    
    def process_product(self, product_mid, iteration):
        """상품 처리 메인 함수 - 세션 미들웨어 사용"""
        try:
            # 네이버 접속 (먼저 페이지 로드)
            self.navigate_to_naver()
            
            # 페이지 로드 후 세션 및 캐시 삭제
            self.session_middleware.clear_all()
            
            # 삭제 확인
            self.session_middleware.verify_clear()
            
            # 메인 키워드 검색
            self.search_main_keyword(self.config.MAIN_KEYWORD)
            
            # 검색어 지우고 새 검색어 입력 (반복 번호 추가)
            search_keyword = f"{self.config.BASE_SEARCH_KEYWORD} {iteration:02d}"
            self.clear_search_and_input_new(search_keyword)
            
            # 제품 하단에 구매 추가정보 버튼 클릭
            self.click_purchase_additional_info()
            
            logger.info(f"상품 {product_mid} 처리 완료 (반복: {iteration:02d})")
            return True
        except Exception as e:
            logger.error(f"상품 처리 중 오류: {e}")
            return False
    
    def close(self):
        """드라이버 종료"""
        if self.driver:
            self.driver.quit()
            logger.info("크롬 드라이버 종료")