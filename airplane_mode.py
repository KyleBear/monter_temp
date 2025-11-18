"""
모바일 Chrome 재시작 + 웹 크롤링 통합 테스트

휴대폰의 Chrome을 껐다 켜면서 네이버 스토어 크롤링을 수행합니다.
- Chrome 재시작 (ADB 사용)
- 네이버 스토어 크롤링 (Selenium 사용)
"""
import time
import logging
from selenium.webdriver.support.ui import WebDriverWait
from crawler import NaverStoreCrawler
from config import Config
from adb_manager import get_adb_manager

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def setup_port_forwarding(adb, port=9222):
    """
    ADB 포트 포워딩 설정 (휴대폰 Chrome 원격 디버깅용)
    
    Args:
        adb: ADB Manager 인스턴스
        port: 포트 번호 (기본값: 9222)
    
    Returns:
        bool: 성공 여부
    """
    try:
        # 기존 포워딩 제거
        try:
            adb.run_command('forward', '--remove', f'tcp:{port}', timeout=3)
        except:
            pass
        
        # 포트 포워딩 설정
        result = adb.run_command('forward', f'tcp:{port}', 'localabstract:chrome_devtools_remote', timeout=5)
        
        if result.returncode == 0:
            logger.info(f"✓ 포트 포워딩 설정 완료 (localhost:{port} -> 기기 Chrome)")
            return True
        else:
            logger.error(f"포트 포워딩 설정 실패: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"포트 포워딩 설정 중 오류: {e}")
        return False


def set_airplane_mode(adb, enable=True):
    """
    비행기 모드 설정/해제
    
    Args:
        adb: ADB Manager 인스턴스
        enable: True면 비행기 모드 켜기, False면 끄기
    
    Returns:
        bool: 성공 여부
    """
    try:
        mode = 1 if enable else 0
        result = adb.run_command('shell', 'settings', 'put', 'global', 'airplane_mode_on', str(mode))
        
        if result.returncode == 0:
            # 비행기 모드 변경을 적용하기 위해 Intent 전송
            intent_action = 'android.settings.AIRPLANE_MODE_SETTINGS'
            adb.run_command('shell', 'am', 'broadcast', '-a', intent_action)
            
            status = "켜기" if enable else "끄기"
            logger.info(f"✓ 비행기 모드 {status} 완료")
            time.sleep(2)  # 설정 적용 대기
            return True
        else:
            logger.error(f"비행기 모드 설정 실패: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"비행기 모드 설정 중 오류: {e}")
        return False


def restart_mobile_chrome(adb, url=None, chrome_package='com.android.chrome'):
    """
    모바일 Chrome 재시작 -- android adb 로 크롬 앱 시작
    
    Args:
        adb: ADB Manager 인스턴스
        url: 시작할 URL (선택사항)
        chrome_package: Chrome 패키지명 (기본: com.android.chrome)
                        여러 Chrome 인스턴스를 위해 다른 패키지명 사용 가능
    
    Returns:
        bool: 성공 여부
    """
    try:
        logger.info("=" * 50)
        logger.info(f"모바일 Chrome 재시작 (패키지: {chrome_package})")
        logger.info("=" * 50)
        
        # Chrome 종료
        logger.info("Chrome 앱 종료 중...")
        result = adb.run_command('shell', 'am', 'force-stop', chrome_package)
        
        if result.returncode == 0:
            logger.info("✓ Chrome 앱 종료 완료")
        else:
            logger.warning(f"Chrome 종료 실패: {result.stderr}")
        
        time.sleep(2)
        
        # Chrome 시작
        if url:
            logger.info(f"Chrome 앱을 {url}로 시작 중...")
            result = adb.run_command('shell', 'am', 'start', '-a', 'android.intent.action.VIEW', 
                                     '-d', url, chrome_package)
        else:
            logger.info("Chrome 앱 시작 중...")
            result = adb.run_command('shell', 'am', 'start', '-n', 
                                     f'{chrome_package}/com.google.android.apps.chrome.Main')
        
        if result.returncode == 0:
            logger.info("✓ Chrome 앱 시작 완료")
            time.sleep(3)
            logger.info("=" * 50)
            return True
        else:
            logger.error(f"Chrome 시작 실패: {result.stderr}")
            logger.info("=" * 50)
            return False
            
    except Exception as e:
        logger.error(f"Chrome 재시작 중 오류: {e}")
        logger.info("=" * 50)
        return False


def run_crawling_task(iteration, use_remote_device=True):
    """
    단일 크롤링 작업 실행
    
    Args:
        iteration: 반복 번호
        use_remote_device: 휴대폰 Chrome 사용 여부
    
    Returns:
        bool: 성공 여부
    """
    config = Config()
    crawler = None
    
    try:
        logger.info("=" * 50)
        logger.info(f"크롤링 작업 시작 - 반복: {iteration:02d}")
        logger.info(f"모드: {'휴대폰 Chrome' if use_remote_device else 'PC Chrome'}")
        logger.info("=" * 50)
        
        # USE_REMOTE_DEVICE 강제 설정 (휴대폰 Chrome 사용)
        original_use_remote = config.USE_REMOTE_DEVICE
        config.USE_REMOTE_DEVICE = use_remote_device
        
        # 프록시 없이 크롤러 생성
        crawler = NaverStoreCrawler(proxy_ip=None)
        
        # 네이버 접속
        crawler.navigate_to_naver()
        
        # 메인 키워드 검색
        main_keyword = config.MAIN_KEYWORD_LIST
        logger.info(f"메인 키워드: {main_keyword}")
        crawler.search_main_keyword(main_keyword)
        
        # 검색어 지우고 새 검색어 입력
        base_keyword = config.BASE_SEARCH_KEYWORD_LIST
        search_keyword = f"{base_keyword} {iteration:02d}"
        logger.info(f"새 검색어: {search_keyword}")
        crawler.clear_search_and_input_new(search_keyword)

        # 검색 결과에서 첫 번째 항목 클릭
        try:
            before_url = crawler.driver.current_url
            logger.info(f"클릭 전 URL: {before_url}")
            
            crawler.driver.execute_script("document.querySelector('ul li.ds9RptR1._slog_visible div.rlwFJ8wP a')?.click();")
            logger.info("검색 결과 첫 번째 항목 링크 클릭 완료")
            
            try:
                WebDriverWait(crawler.driver, 10).until(
                    lambda driver: driver.current_url != before_url
                )
                after_url = crawler.driver.current_url
                logger.info(f"클릭 후 URL: {after_url}")
                logger.info("✓ 링크 이동 성공")
            except:
                after_url = crawler.driver.current_url
                logger.warning(f"⚠ URL 변경이 감지되지 않았습니다 (현재 URL: {after_url})")
            
            time.sleep(2)
        except Exception as e:
            logger.warning(f"검색 결과 첫 번째 항목 클릭 실패: {e}")
        
        # 제품 하단에 구매 추가정보 버튼 클릭
        crawler.click_purchase_additional_info()

        # 임시 검색어로 재검색
        temp_search_keyword = config.TEMP_SEARCH_KEYWORD_LIST 
        crawler.clear_search_and_input_new(temp_search_keyword)
        
        # 다시 첫 번째 항목 클릭
        try:
            before_url = crawler.driver.current_url
            logger.info(f"클릭 전 URL: {before_url}")
            
            crawler.driver.execute_script("document.querySelector('ul li.ds9RptR1._slog_visible div.rlwFJ8wP a')?.click();")
            logger.info("검색 결과 첫 번째 항목 링크 클릭 완료")
            
            try:
                WebDriverWait(crawler.driver, 10).until(
                    lambda driver: driver.current_url != before_url
                )
                after_url = crawler.driver.current_url
                logger.info(f"클릭 후 URL: {after_url}")
                logger.info("✓ 링크 이동 성공")
            except:
                after_url = crawler.driver.current_url
                logger.warning(f"⚠ URL 변경이 감지되지 않았습니다 (현재 URL: {after_url})")
            time.sleep(2)
        except Exception as e:
            logger.warning(f"검색 결과 첫 번째 항목 클릭 실패: {e}")        
        
        # 제품 하단에 구매 추가정보 버튼 클릭
        crawler.click_purchase_additional_info()

        logger.info(f"크롤링 작업 완료 - 반복: {iteration:02d}")
        return True
        
    except Exception as e:
        logger.error(f"크롤링 중 오류 발생: {e}", exc_info=True)
        return False
    finally:
        if crawler:
            crawler.close()
        # 원래 설정 복원
        config.USE_REMOTE_DEVICE = original_use_remote
        time.sleep(2)


def test_mobile_chrome_with_crawling(
    restart_chrome_each_iteration=True,
    enable_airplane_mode_on_finish=True,
    use_multiple_chrome=False
):
    """
    모바일 Chrome 재시작 + 크롤링 통합 테스트
    
    Args:
        restart_chrome_each_iteration: 각 반복마다 Chrome을 재시작할지 여부
        enable_airplane_mode_on_finish: 테스트 종료 시 비행기 모드 켜기
        use_multiple_chrome: 여러 Chrome 인스턴스 사용 여부
    """
    config = Config()
    logger.info("=" * 70)
    logger.info("모바일 Chrome 재시작 + 네이버 스토어 크롤링 통합 테스트")
    logger.info("=" * 70)
    logger.info(f"메인 키워드: {config.MAIN_KEYWORD_LIST}")
    logger.info(f"기본 검색 키워드: {config.BASE_SEARCH_KEYWORD_LIST}")
    logger.info(f"반복 횟수: {config.REPEAT_COUNT}")
    logger.info(f"Chrome 재시작: {'매 반복마다' if restart_chrome_each_iteration else '처음 한번만'}")
    logger.info(f"비행기 모드: {'종료 시 켜기' if enable_airplane_mode_on_finish else '사용 안함'}")
    logger.info(f"여러 Chrome: {'사용' if use_multiple_chrome else '사용 안함'}")
    logger.info("=" * 70)
    
    # ADB Manager 초기화
    adb = get_adb_manager()
    
    # ADB 연결 확인
    if not adb.check_connection():
        logger.error("⚠ ADB 연결 실패. 테스트를 중단합니다.")
        logger.error("휴대폰이 USB로 연결되어 있고 USB 디버깅이 활성화되어 있는지 확인하세요.")
        return False
    
    # 포트 포워딩 설정 (휴대폰 Chrome 원격 디버깅용)
    logger.info("\n포트 포워딩 설정 중...")
    if not setup_port_forwarding(adb, config.REMOTE_DEBUGGING_PORT):
        logger.warning("⚠ 포트 포워딩 설정 실패했지만 계속 진행합니다...")
    
    # 네이버 모바일 URL
    naver_url = config.NAVER_MOBILE_URL if hasattr(config, 'NAVER_MOBILE_URL') else None
    
    # 여러 Chrome 패키지명 (필요시 추가)
    chrome_packages = ['com.android.chrome']  # 기본 Chrome
    if use_multiple_chrome:
        # Chrome Beta, Dev 등 추가 가능
        chrome_packages.extend([
            'com.chrome.beta',
            'com.chrome.dev',
        ])
    
    # 처음 한 번 Chrome 재시작
    if not restart_chrome_each_iteration:
        logger.info("\n[초기 Chrome 재시작]")
        if not restart_mobile_chrome(adb, naver_url, chrome_packages[0]):
            logger.warning("⚠ Chrome 재시작 실패했지만 계속 진행합니다...")
        time.sleep(3)
    
    # 반복 테스트
    success_count = 0
    try:
        for iteration in range(config.REPEAT_COUNT):
            logger.info("\n" + "=" * 70)
            logger.info(f"[반복 {iteration + 1}/{config.REPEAT_COUNT}] 시작")
            logger.info("=" * 70)
            
            # 여러 Chrome 사용 시 순환
            chrome_package = chrome_packages[iteration % len(chrome_packages)]
            
            # 각 반복마다 Chrome 재시작 (옵션)
            if restart_chrome_each_iteration:
                logger.info(f"\n>> Chrome 재시작 ({iteration + 1}/{config.REPEAT_COUNT})")
                logger.info(f"   패키지: {chrome_package}")
                if not restart_mobile_chrome(adb, naver_url, chrome_package):
                    logger.warning("⚠ Chrome 재시작 실패했지만 계속 진행합니다...")
                time.sleep(3)
            
            # 크롤링 작업 수행
            logger.info(f"\n>> 크롤링 작업 ({iteration + 1}/{config.REPEAT_COUNT})")
            success = run_crawling_task(iteration, use_remote_device=True)
            
            if success:
                success_count += 1
                logger.info(f"✓ 반복 {iteration:02d} 성공")
            else:
                logger.warning(f"⚠ 반복 {iteration:02d} 실패")
            
            # 마지막이 아니면 대기
            if iteration < config.REPEAT_COUNT - 1:
                wait_time = config.ACTION_DELAY if hasattr(config, 'ACTION_DELAY') else 5
                logger.info(f"\n다음 반복까지 {wait_time}초 대기...")
                time.sleep(wait_time)
    finally:
        # 테스트 종료 시 비행기 모드 켜기
        if enable_airplane_mode_on_finish:
            logger.info("\n" + "=" * 70)
            logger.info("테스트 종료 - 비행기 모드 켜기")
            logger.info("=" * 70)
            set_airplane_mode(adb, enable=True)
    
    # 최종 결과
    logger.info("\n" + "=" * 70)
    logger.info("테스트 완료")
    logger.info(f"성공: {success_count}/{config.REPEAT_COUNT}")
    logger.info("=" * 70)
    
    return success_count == config.REPEAT_COUNT


def main():
    """메인 함수"""
    # 옵션 선택
    restart_each_iteration = True  # True: 매번 재시작, False: 처음 한번만
    enable_airplane_mode = True    # True: 종료 시 비행기 모드 켜기
    use_multiple_chrome = False    # True: 여러 Chrome 인스턴스 사용
    
    test_mobile_chrome_with_crawling(
        restart_chrome_each_iteration=restart_each_iteration,
        enable_airplane_mode_on_finish=enable_airplane_mode,
        use_multiple_chrome=use_multiple_chrome
    )


if __name__ == '__main__':
    main()
