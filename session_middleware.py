"""
세션 및 캐시 관리 미들웨어
각 요청 전에 세션과 캐시를 자동으로 정리하는 기능 제공
"""
from selenium.webdriver.remote.webdriver import WebDriver
import logging

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

