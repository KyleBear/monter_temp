"""
휴대폰 데이터 연결 끄기/켜기 테스트
ADB를 사용하여 휴대폰의 데이터 연결을 끄고 켭니다.
"""
import time
import logging
from adb_manager import get_adb_manager

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DataConnectionManager:
    """데이터 연결 관리 클래스"""
    
    def __init__(self, adb=None):
        """
        초기화
        
        Args:
            adb: ADB Manager 인스턴스 (None이면 자동으로 가져옴)
        """
        if adb is None:
            self.adb = get_adb_manager()
        else:
            self.adb = adb
        
        # ADB 연결 확인
        if not self.adb.check_connection():
            logger.warning("⚠ ADB 연결 실패. 연결을 확인하세요.")
    
    def disable_data(self):
        """
        데이터 연결 끄기
        
        Returns:
            bool: 성공 여부
        """
        try:
            logger.info("데이터 연결 끄기 시작...")
            result = self.adb.run_command("shell", "svc", "data", "disable")
            
            if result.returncode == 0:
                logger.info("✓ 데이터 연결 끄기 완료")
                return True
            else:
                logger.warning(f"데이터 연결 끄기 실패: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"데이터 연결 끄기 중 오류: {e}")
            return False
    
    def enable_data(self):
        """
        데이터 연결 켜기
        
        Returns:
            bool: 성공 여부
        """
        try:
            logger.info("데이터 연결 켜기 시작...")
            result = self.adb.run_command("shell", "svc", "data", "enable")
            
            if result.returncode == 0:
                logger.info("✓ 데이터 연결 켜기 완료")
                return True
            else:
                logger.warning(f"데이터 연결 켜기 실패: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"데이터 연결 켜기 중 오류: {e}")
            return False
    
    def toggle_data_connection(self, disable_duration=2):
        """
        데이터 연결 끄기/켜기 (IP 변경용)
        
        Args:
            disable_duration: 데이터를 끈 상태로 유지할 시간(초)
        
        Returns:
            bool: 성공 여부
        """
        try:
            # 데이터 연결 끄기
            if not self.disable_data():
                return False
            
            # 대기 시간
            logger.info(f"데이터 연결 끈 상태로 {disable_duration}초 대기...")
            time.sleep(disable_duration)
            
            # 데이터 연결 켜기
            if not self.enable_data():
                return False
            
            logger.info("✓ 데이터 연결 토글 완료")
            return True
            
        except Exception as e:
            logger.error(f"데이터 연결 토글 중 오류: {e}")
            return False


def main():
    """메인 함수 (사용 예제)"""
    logger.info("=" * 70)
    logger.info("데이터 연결 끄기/켜기 테스트 시작")
    logger.info("=" * 70)
    
    # 클래스 인스턴스 생성
    data_manager = DataConnectionManager()
    
    # ADB 연결 확인
    if not data_manager.adb.check_connection():
        logger.error("⚠ ADB 연결 실패. 테스트를 중단합니다.")
        logger.error("휴대폰이 USB로 연결되어 있고 USB 디버깅이 활성화되어 있는지 확인하세요.")
        return False
    
    # 데이터 연결 끄기/켜기 실행
    success = data_manager.toggle_data_connection(disable_duration=2)
    
    if success:
        logger.info("=" * 70)
        logger.info("✓ 테스트 완료")
        logger.info("=" * 70)
    else:
        logger.error("=" * 70)
        logger.error("⚠ 테스트 실패")
        logger.error("=" * 70)
    
    return success


if __name__ == '__main__':
    main()