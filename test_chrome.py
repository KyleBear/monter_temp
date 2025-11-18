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

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_single_iteration(iteration):
    """단일 반복 테스트"""
    config = Config()
    crawler = None
    
    try:
        logger.info("=" * 50)
        logger.info(f"테스트 시작 - 반복: {iteration:02d}")
        logger.info("=" * 50)
        
        # 프록시 없이 크롤러 생성
        # crawler = NaverStoreCrawler(proxy_ip=None)
        crawler = NaverStoreCrawler()        
        # 네이버 접속 (먼저 페이지 로드)
        crawler.navigate_to_naver()
        
        # 메인 키워드 검색 (config.py의 MAIN_KEYWORD_LIST 사용)
        main_keyword = config.MAIN_KEYWORD_LIST
        logger.info(f"메인 키워드: {main_keyword}")
        crawler.search_main_keyword(main_keyword)
        
        # 검색어 지우고 새 검색어 입력 (반복 번호 추가)
        base_keyword = config.BASE_SEARCH_KEYWORD_LIST
        search_keyword = f"{base_keyword} {iteration:02d}"
        logger.info(f"새 검색어: {search_keyword}")
        crawler.clear_search_and_input_new(search_keyword)

        # 검색 결과에서 첫 번째 항목 클릭 (ul 아래의 li 중 class가 "ds9RptR1 _slog_visible" 인 첫 번째 요소의 링크)
        try:
            # 클릭 전 URL 저장
            before_url = crawler.driver.current_url
            logger.info(f"클릭 전 URL: {before_url}")
            
            # 첫 번째 항목의 링크 클릭 (div.rlwFJ8wP 안의 a 태그)
            crawler.driver.execute_script("document.querySelector('ul li.ds9RptR1._slog_visible div.rlwFJ8wP a')?.click();")
            logger.info("검색 결과 첫 번째 항목 링크 클릭 완료")
            
            # 페이지 로드 대기 (URL 변경 확인)
            try:
                WebDriverWait(crawler.driver, 10).until(
                    lambda driver: driver.current_url != before_url
                )
                after_url = crawler.driver.current_url
                logger.info(f"클릭 후 URL: {after_url}")
                logger.info("✓ 링크 이동 성공")
            except:
                # URL이 변경되지 않았거나 타임아웃
                after_url = crawler.driver.current_url
                logger.warning(f"⚠ URL 변경이 감지되지 않았습니다 (현재 URL: {after_url})")
            
            time.sleep(2)  # 클릭 후 2초 대기
        except Exception as e:
            logger.warning(f"검색 결과 첫 번째 항목 클릭 실패: {e}")
        
        # 제품 하단에 구매 추가정보 버튼 클릭
        crawler.click_purchase_additional_info()

        temp_search_keyword = config.TEMP_SEARCH_KEYWORD_LIST 
        crawler.clear_search_and_input_new(temp_search_keyword)
        
        # 검색 결과에서 첫 번째 항목 클릭 (ul 아래의 li 중 class가 "ds9RptR1 _slog_visible" 인 첫 번째 요소의 링크)
        try:
            # 클릭 전 URL 저장
            before_url = crawler.driver.current_url
            logger.info(f"클릭 전 URL: {before_url}")
            
            # 첫 번째 항목의 링크 클릭 (div.rlwFJ8wP 안의 a 태그)
            crawler.driver.execute_script("document.querySelector('ul li.ds9RptR1._slog_visible div.rlwFJ8wP a')?.click();")
            logger.info("검색 결과 첫 번째 항목 링크 클릭 완료")
            
            # 페이지 로드 대기 (URL 변경 확인)
            try:
                WebDriverWait(crawler.driver, 10).until(
                    lambda driver: driver.current_url != before_url
                )
                after_url = crawler.driver.current_url
                logger.info(f"클릭 후 URL: {after_url}")
                logger.info("✓ 링크 이동 성공")
            except:
                # URL이 변경되지 않았거나 타임아웃
                after_url = crawler.driver.current_url
                logger.warning(f"⚠ URL 변경이 감지되지 않았습니다 (현재 URL: {after_url})")
            
            time.sleep(2)  # 클릭 후 2초 대기
        except Exception as e:
            logger.warning(f"검색 결과 첫 번째 항목 클릭 실패: {e}")
        
        # 제품 하단에 구매 추가정보 버튼 클릭
        crawler.click_purchase_additional_info()

        logger.info(f"테스트 완료 - 반복: {iteration:02d}")
        return True
        
    except Exception as e:
        logger.error(f"테스트 중 오류 발생: {e}", exc_info=True)
        return False
    finally:
        if crawler:
            crawler.close()
        time.sleep(2)


def main():
    """메인 테스트 함수"""
    config = Config()
    
    logger.info("=" * 50)
    logger.info("네이버 스토어 크롤링 테스트 시작")
    logger.info("주의사항 1,2,3 무시 모드")
    logger.info("=" * 50)
    logger.info(f"메인 키워드: {config.MAIN_KEYWORD_LIST}")
    logger.info(f"기본 검색 키워드: {config.BASE_SEARCH_KEYWORD_LIST}")
    logger.info(f"반복 횟수: {config.REPEAT_COUNT}")
    logger.info("=" * 50)
    
    # 4번 반복 (00, 01, 02, 03)
    for iteration in range(config.REPEAT_COUNT):
        logger.info(f"\n[반복 {iteration + 1}/{config.REPEAT_COUNT}]")
        success = test_single_iteration(iteration)
        
        if success:
            logger.info(f"반복 {iteration:02d} 성공")
        else:
            logger.warning(f"반복 {iteration:02d} 실패")
        
        # 마지막 반복이 아니면 대기
        if iteration < config.REPEAT_COUNT - 1:
            logger.info(f"다음 반복까지 {config.ACTION_DELAY}초 대기...")
            time.sleep(config.ACTION_DELAY)
    
    logger.info("=" * 50)
    logger.info("모든 테스트 완료")
    logger.info("=" * 50)


if __name__ == '__main__':
    main()