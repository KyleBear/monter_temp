"""
포트 9222, 9223을 사용하는 프로세스 종료 스크립트
"""
import logging
from port_manager import PortManager

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

if __name__ == '__main__':
    manager = PortManager()
    
    print("=" * 50)
    print("포트 9222, 9223 해제 중...")
    print("=" * 50)
    
    # 포트 해제
    results = manager.free_ports([9222, 9223], force=True, wait_time=2)
    
    print("\n" + "=" * 50)
    print("포트 해제 결과:")
    print("=" * 50)
    for port, success in results.items():
        status = "[성공]" if success else "[실패]"
        print(f"포트 {port}: {status}")
    
    print("=" * 50)

