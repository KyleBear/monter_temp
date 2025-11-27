"""
m.naver.com의 쿠키를 수집하여 JSON 파일로 저장하는 스크립트
PyScheduler로 스케줄링하여 실행
"""

import time
import logging
import json
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from proxy_config.proxy_chain import WHITELIST_PROXIES

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('cookie_collection.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class NaverCookieCollector:
    """네이버 쿠키 수집 클래스 (순수 수집만 담당)"""
    
    def __init__(self, use_proxy=True, proxy_index=None):
        """
        Args:
            use_proxy: 프록시 사용 여부 (기본값: True)
            proxy_index: 프록시 인덱스 (선택사항)
        """
        self.driver = None
        self.use_proxy = use_proxy
        self.proxy_index = proxy_index
        self.current_proxy = None
        self._setup_driver()
    
    def _setup_driver(self):
        """Chrome 드라이버 설정"""
        logger.info("[드라이버 설정] Chrome 드라이버 설정 시작...")
        
        # Chrome 옵션 설정
        options = Options()
        
        # ChromeDriver 경로 설정
        chrome_138_directory = "chrome_138_directory"
        chromedriver_path = os.path.join(chrome_138_directory, "chromedriver.exe")
        
        if not os.path.exists(chromedriver_path):
            logger.error(f"ChromeDriver 파일을 찾을 수 없습니다: {chromedriver_path}")
            raise FileNotFoundError(f"ChromeDriver 파일을 찾을 수 없습니다: {chromedriver_path}")
        
        service = Service(chromedriver_path)
        logger.info(f"[드라이버 설정] ChromeDriver 경로: {chromedriver_path}")
        
        # ⭐ Chrome 바이너리 경로 지정 (중요!)
        # 사용자 지정 경로 우선 확인
        chrome_binary_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",  # 사용자 지정 경로 (우선)
            os.path.join(chrome_138_directory, "chrome.exe"),  # 기존 경로
        ]
        
        chrome_binary_path = None
        for path in chrome_binary_paths:
            if os.path.exists(path):
                chrome_binary_path = path
                options.binary_location = path
                logger.info(f"[드라이버 설정] Chrome 바이너리 경로 지정: {path}")
                break
        
        if not chrome_binary_path:
            # Chrome 바이너리를 찾을 수 없는 경우
            logger.warning(f"[드라이버 설정] Chrome 바이너리를 찾을 수 없습니다: {chrome_binary_path}")
            raise FileNotFoundError(f"Chrome 바이너리를 찾을 수 없습니다: {chrome_binary_path}")
        
        # 프록시 설정 (proxy_chain.py를 통해)
        if self.use_proxy:
            options.add_argument('--proxy-server=socks5://127.0.0.1:1080')
            # 현재 사용 중인 프록시 정보 로깅
            if self.proxy_index is not None and self.proxy_index < len(WHITELIST_PROXIES):
                proxy = WHITELIST_PROXIES[self.proxy_index]
                self.current_proxy = f"{proxy['host']}:{proxy['port']}"
                logger.info(f"[프록시] proxy_chain을 통한 프록시 설정: socks5://127.0.0.1:1080 (원격: {self.current_proxy})")
            else:
                logger.info("[프록시] proxy_chain을 통한 프록시 설정: socks5://127.0.0.1:1080")
        
        # 기본 옵션
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36')
        
        # 자동화 탐지 제거 옵션
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        # Chrome 로그 오류 억제
        options.add_argument("--disable-logging")
        options.add_argument("--log-level=3")
        options.add_argument("--disable-gcm")
        
        # Headless 모드 (백그라운드 실행)
        # options.add_argument('--headless=new')
        # options.add_argument('--disable-gpu')
        # options.add_argument('--window-size=1920,1080')
        
        try:
            self.driver = webdriver.Chrome(service=service, options=options)
            logger.info("[드라이버 설정] Chrome 드라이버 생성 성공")
        except Exception as e:
            logger.error(f"[드라이버 설정] Chrome 드라이버 생성 실패: {e}", exc_info=True)
            raise
    
    def collect_cookies(self):
        """
        m.naver.com의 모든 쿠키 수집 (NNB, BUC, NAC 등 포함)
        페이지 상호작용을 통해 쿠키 생성 유도
        
        Returns:
            list: 쿠키 리스트
        """
        try:
            logger.info("[쿠키 수집] m.naver.com 접속 중...")
            self.driver.get("https://m.naver.com")
            
            # 페이지 완전 로드 대기
            time.sleep(3)
            
            # 중요 쿠키 목록 (Readme.md 참고)
            important_cookies = ['NNB', 'BUC', 'NAC', 'NACT', '_naver_usersession_', 
                               'MM_PF', 'MM_search_homefeed', 'SRT30', 'SRT5']
            
            # 쿠키 생성 유도를 위한 상호작용
            logger.info("[쿠키 수집] 쿠키 생성 유도를 위한 페이지 상호작용 중...")
            
            # 1. 스크롤 동작 (쿠키 생성 유도)
            try:
                self.driver.execute_script("window.scrollTo(0, 500);")
                time.sleep(2)
                self.driver.execute_script("window.scrollTo(0, 1000);")
                time.sleep(2)
                self.driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(2)
                logger.info("[쿠키 수집] 스크롤 동작 완료")
            except Exception as e:
                logger.debug(f"[쿠키 수집] 스크롤 동작 중 오류: {e}")
            
            # 2. 여러 번 쿠키 확인 (쿠키가 점진적으로 생성됨)
            max_attempts = 5
            all_cookies = []
            found_important = set()
            
            for attempt in range(max_attempts):
                cookies = self.driver.get_cookies()
                
                # 중복 제거하여 추가
                existing_names = {c.get('name') for c in all_cookies}
                for cookie in cookies:
                    if cookie.get('name') not in existing_names:
                        all_cookies.append(cookie)
                        existing_names.add(cookie.get('name'))
                
                # 중요 쿠키 확인
                current_names = {c.get('name') for c in cookies}
                for imp_cookie in important_cookies:
                    if imp_cookie in current_names:
                        found_important.add(imp_cookie)
                
                logger.info(f"[쿠키 수집] 시도 {attempt + 1}/{max_attempts}: {len(cookies)}개 쿠키 발견 (중요: {len(found_important)}/{len(important_cookies)})")
                
                # 중요 쿠키가 충분히 생성되었는지 확인
                if len(found_important) >= 5:  # 최소 5개 이상의 중요 쿠키
                    logger.info(f"[쿠키 수집] 중요 쿠키 충분히 생성됨: {found_important}")
                    break
                
                # 추가 상호작용 (검색창 클릭 등)
                if attempt < max_attempts - 1:
                    try:
                        # 검색창 클릭 (쿠키 생성 유도)
                        search_input = self.driver.execute_script("""
                            var input = document.querySelector('input[type="search"]') || 
                                       document.querySelector('#query') ||
                                       document.querySelector('.sch_input');
                            if (input) {
                                input.click();
                                input.focus();
                                return true;
                            }
                            return false;
                        """)
                        if search_input:
                            time.sleep(1)
                    except:
                        pass
                    
                    time.sleep(2)  # 쿠키 생성 대기
            
            # 최종 쿠키 수집
            final_cookies = self.driver.get_cookies()
            existing_names = {c.get('name') for c in all_cookies}
            for cookie in final_cookies:
                if cookie.get('name') not in existing_names:
                    all_cookies.append(cookie)
            
            logger.info(f"[쿠키 수집] 총 {len(all_cookies)}개의 쿠키 수집 완료")
            
            # 중요 쿠키 확인 및 로깅
            cookie_names = {c.get('name') for c in all_cookies}
            found_important_final = cookie_names.intersection(set(important_cookies))
            missing_important = set(important_cookies) - found_important_final
            
            logger.info(f"[쿠키 수집] 중요 쿠키 수집 현황:")
            logger.info(f"  ✓ 수집됨 ({len(found_important_final)}개): {', '.join(sorted(found_important_final))}")
            if missing_important:
                logger.warning(f"  ✗ 누락됨 ({len(missing_important)}개): {', '.join(sorted(missing_important))}")
            
            # 모든 쿠키 정보 로깅 (도메인별)
            cookie_by_domain = {}
            for cookie in all_cookies:
                domain = cookie.get('domain', 'unknown')
                if domain not in cookie_by_domain:
                    cookie_by_domain[domain] = []
                cookie_by_domain[domain].append(cookie.get('name'))
            
            for domain, names in cookie_by_domain.items():
                logger.info(f"[쿠키 수집] {domain}: {len(names)}개 쿠키")
                logger.debug(f"  쿠키 목록: {', '.join(names)}")
            
            return all_cookies
            
        except Exception as e:
            logger.error(f"[쿠키 수집] 쿠키 수집 실패: {e}", exc_info=True)
            return []
    
    def save_cookies_to_json(self, cookies, output_dir="cookies_data", proxy_info=None):
        """
        쿠키를 JSON 파일로 저장 (NNB 교체 없이 순수 저장)
        
        Args:
            cookies: 쿠키 리스트
            output_dir: 출력 디렉토리 (기본값: cookies_data)
            proxy_info: 프록시 정보 (선택사항)
        
        Returns:
            str: 저장된 파일 경로
        """
        try:
            # 출력 디렉토리 생성
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
                logger.info(f"[파일 저장] 디렉토리 생성: {output_dir}")
            
            # 파일명: naver_cookies_YYYY-MM-DD_HH-MM-SS_proxy-{index}.json
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            if proxy_info is not None:
                filename = f"naver_cookies_{timestamp}_proxy-{proxy_info}.json"
            else:
                filename = f"naver_cookies_{timestamp}.json"
            filepath = os.path.join(output_dir, filename)
            
            # 쿠키 데이터 구조화 (NNB 교체 없이)
            cookie_data = {
                "collection_time": datetime.now().isoformat(),
                "domain": "m.naver.com",
                "proxy": self.current_proxy if self.current_proxy else None,
                "proxy_index": self.proxy_index,
                "total_cookies": len(cookies),
                "cookies": cookies
            }
            
            # JSON 파일로 저장
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(cookie_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"[파일 저장] 쿠키 저장 완료: {filepath}")
            logger.info(f"[파일 저장] 총 {len(cookies)}개의 쿠키 저장됨")
            
            return filepath
            
        except Exception as e:
            logger.error(f"[파일 저장] 쿠키 저장 실패: {e}", exc_info=True)
            return None
    
    def close(self):
        """드라이버 종료"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("[드라이버 종료] Chrome 드라이버 종료 완료")
            except Exception as e:
                logger.error(f"[드라이버 종료] 드라이버 종료 중 오류: {e}")


def collect_naver_cookies(proxy_index=None):
    """
    네이버 쿠키 수집 및 저장 메인 함수
    PyScheduler에서 호출하기 위한 함수
    
    Args:
        proxy_index: 프록시 인덱스 (선택사항, None이면 자동 선택)
    
    Returns:
        bool: 성공 여부
    """
    collector = None
    try:
        logger.info("=" * 60)
        logger.info("네이버 쿠키 수집 시작")
        if proxy_index is not None:
            logger.info(f"프록시 인덱스: {proxy_index}")
        logger.info("=" * 60)
        
        # 쿠키 수집기 생성
        collector = NaverCookieCollector(use_proxy=True, proxy_index=proxy_index)
        
        # 쿠키 수집
        cookies = collector.collect_cookies()
        
        if cookies:
            # JSON 파일로 저장
            filepath = collector.save_cookies_to_json(cookies, proxy_info=proxy_index)
            if filepath:
                logger.info("=" * 60)
                logger.info("✓ 네이버 쿠키 수집 및 저장 완료")
                logger.info(f"저장 위치: {filepath}")
                logger.info("=" * 60)
                return True
            else:
                logger.error("쿠키 저장 실패")
                return False
        else:
            logger.warning("수집된 쿠키가 없습니다")
            return False
            
    except Exception as e:
        logger.error(f"쿠키 수집 중 오류 발생: {e}", exc_info=True)
        return False
    finally:
        if collector:
            collector.close()


def collect_cookies_for_all_proxies():
    """
    모든 프록시에 대해 쿠키 수집 (프록시 IP 변경 시마다)
    PyScheduler에서 호출하기 위한 함수
    
    Returns:
        list: 결과 리스트
    """
    logger.info("=" * 60)
    logger.info("모든 프록시에 대한 쿠키 수집 시작")
    logger.info(f"총 {len(WHITELIST_PROXIES)}개의 프록시")
    logger.info("=" * 60)
    
    results = []
    for i, proxy in enumerate(WHITELIST_PROXIES):
        logger.info(f"\n[{i+1}/{len(WHITELIST_PROXIES)}] 프록시 {i}: {proxy['host']}:{proxy['port']}")
        success = collect_naver_cookies(proxy_index=i)
        results.append({
            'proxy_index': i,
            'proxy': proxy,
            'success': success
        })
        
        # 다음 프록시로 넘어가기 전 대기
        if i < len(WHITELIST_PROXIES) - 1:
            time.sleep(5)  # 5초 대기
    
    # 결과 요약
    success_count = sum(1 for r in results if r['success'])
    logger.info("=" * 60)
    logger.info(f"쿠키 수집 완료: {success_count}/{len(results)} 성공")
    logger.info("=" * 60)
    
    return results


if __name__ == '__main__':
    import sys
    
    # 명령줄 인자 확인
    if len(sys.argv) > 1 and sys.argv[1] == '--all':
        # 모든 프록시에 대해 수집
        collect_cookies_for_all_proxies()
    elif len(sys.argv) > 1 and sys.argv[1].isdigit():
        # 특정 프록시 인덱스에 대해 수집
        proxy_index = int(sys.argv[1])
        collect_naver_cookies(proxy_index=proxy_index)
    else:
        # 기본: 첫 번째 프록시에 대해 수집
        logger.info("기본 모드: 첫 번째 프록시에 대해 쿠키 수집")
        collect_naver_cookies(proxy_index=0)
