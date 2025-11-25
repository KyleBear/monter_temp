"""
프록시 로테이션 및 관리 모듈
iplist.txt에서 프록시 목록을 읽어서 순환하면서 사용합니다.
비동기 프록시 테스트 기능 포함.
"""
import os
import logging
import asyncio
import aiohttp
import time
from typing import List, Optional, Iterator, Dict
from itertools import cycle

logger = logging.getLogger(__name__)

TEST_URL = "https://api.ipify.org?format=json"


class ProxyRotator:
    """
    iplist.txt에서 프록시 목록을 읽어서 순환하면서 반환하는 클래스
    """
    
    def __init__(self, ip_list_file: str = "iplist.txt"):
        """
        Args:
            ip_list_file: 프록시 IP 목록이 있는 파일 경로 (기본값: iplist.txt)
        """
        self.ip_list_file = ip_list_file
        self.proxy_list: List[str] = []
        self.proxy_cycle: Optional[Iterator[str]] = None
        self.current_index = 0
        
        # 프록시 목록 로드
        self.load_proxies()
    
    def load_proxies(self) -> bool:
        """
        iplist.txt 파일에서 프록시 목록을 읽어옵니다.
        
        Returns:
            bool: 성공 여부
        """
        try:
            # 파일 경로 확인 (현재 디렉토리 또는 상위 디렉토리)
            file_paths = [
                self.ip_list_file,
                os.path.join(os.path.dirname(os.path.dirname(__file__)), self.ip_list_file),
                os.path.join(os.path.dirname(__file__), self.ip_list_file)
            ]
            
            file_path = None
            for path in file_paths:
                if os.path.exists(path):
                    file_path = path
                    break
            
            if not file_path:
                logger.error(f"프록시 목록 파일을 찾을 수 없습니다: {self.ip_list_file}")
                logger.error(f"시도한 경로: {file_paths}")
                return False
            
            # 파일 읽기
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 프록시 목록 파싱
            self.proxy_list = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):  # 빈 줄과 주석 제외
                    # IP:포트 형식 검증
                    if ':' in line:
                        self.proxy_list.append(line)
                    else:
                        logger.warning(f"잘못된 프록시 형식 (무시됨): {line}")
            
            if not self.proxy_list:
                logger.error("유효한 프록시가 없습니다.")
                return False
            
            # 순환 반복자 생성
            self.proxy_cycle = cycle(self.proxy_list)
            logger.info(f"프록시 목록 로드 완료: {len(self.proxy_list)}개")
            logger.info(f"프록시 목록: {self.proxy_list}")
            return True
            
        except Exception as e:
            logger.error(f"프록시 목록 로드 실패: {e}", exc_info=True)
            return False
    
    def get_next_proxy(self) -> Optional[str]:
        """
        다음 프록시를 반환합니다 (순환).
        
        Returns:
            str: 프록시 주소 (IP:포트 형식), 실패 시 None
        """
        if not self.proxy_cycle:
            logger.error("프록시 목록이 로드되지 않았습니다.")
            return None
        
        try:
            proxy = next(self.proxy_cycle)
            self.current_index = (self.current_index + 1) % len(self.proxy_list)
            logger.info(f"다음 프록시 선택: {proxy} (인덱스: {self.current_index}/{len(self.proxy_list)})")
            return proxy
        except Exception as e:
            logger.error(f"프록시 가져오기 실패: {e}")
            return None
    
    def get_proxy_at_index(self, index: int) -> Optional[str]:
        """
        특정 인덱스의 프록시를 반환합니다.
        
        Args:
            index: 프록시 인덱스 (0부터 시작)
        
        Returns:
            str: 프록시 주소, 실패 시 None
        """
        if not self.proxy_list:
            logger.error("프록시 목록이 로드되지 않았습니다.")
            return None
        
        if index < 0 or index >= len(self.proxy_list):
            logger.error(f"인덱스 범위를 벗어났습니다: {index} (범위: 0-{len(self.proxy_list)-1})")
            return None
        
        return self.proxy_list[index]
    
    def get_current_proxy(self) -> Optional[str]:
        """
        현재 프록시를 반환합니다.
        
        Returns:
            str: 현재 프록시 주소, 없으면 None
        """
        if not self.proxy_list:
            return None
        
        return self.proxy_list[self.current_index % len(self.proxy_list)]
    
    def get_all_proxies(self) -> List[str]:
        """
        모든 프록시 목록을 반환합니다.
        
        Returns:
            List[str]: 프록시 목록
        """
        return self.proxy_list.copy()
    
    def get_proxy_count(self) -> int:
        """
        프록시 개수를 반환합니다.
        
        Returns:
            int: 프록시 개수
        """
        return len(self.proxy_list)
    
    def reset(self):
        """
        프록시 순환을 처음부터 다시 시작합니다.
        """
        if self.proxy_list:
            self.proxy_cycle = cycle(self.proxy_list)
            self.current_index = 0
            logger.info("프록시 순환 리셋 완료")


# 전역 인스턴스 (싱글톤 패턴)
_proxy_rotator: Optional[ProxyRotator] = None


def get_proxy_rotator(ip_list_file: str = "iplist.txt") -> ProxyRotator:
    """
    ProxyRotator 싱글톤 인스턴스를 반환합니다.
    
    Args:
        ip_list_file: 프록시 IP 목록 파일 경로
    
    Returns:
        ProxyRotator: ProxyRotator 인스턴스
    """
    global _proxy_rotator
    if _proxy_rotator is None:
        _proxy_rotator = ProxyRotator(ip_list_file)
    return _proxy_rotator


def get_next_proxy() -> Optional[str]:
    """
    다음 프록시를 반환합니다 (편의 함수).
    
    Returns:
        str: 프록시 주소 (IP:포트 형식), 실패 시 None
    """
    rotator = get_proxy_rotator()
    return rotator.get_next_proxy()


def get_proxy_for_chrome_options(proxy: Optional[str] = None, proxy_type: str = 'socks5') -> dict:
    """
    Chrome 옵션에 사용할 프록시 설정을 반환합니다.
    
    Args:
        proxy: 프록시 주소 (None이면 자동으로 다음 프록시 선택)
        proxy_type: 프록시 타입 ('http' 또는 'socks5', 기본값: 'socks5')
    
    Returns:
        dict: Chrome 옵션에 추가할 프록시 설정
            {
                'proxy': 'IP:포트',
                'proxy_type': 'socks5' 또는 'http',
                'chrome_option': '--proxy-server=socks5://IP:포트' 또는 '--proxy-server=http://IP:포트'
            }
    """
    if proxy is None:
        proxy = get_next_proxy()
    
    if not proxy:
        logger.warning("프록시를 사용할 수 없습니다.")
        return {}
    
    # 프록시 타입에 따라 URL 형식 결정
    proxy_type_lower = proxy_type.lower()
    if proxy_type_lower == 'socks5':
        proxy_url = f'socks5://{proxy}'
    elif proxy_type_lower == 'http':
        proxy_url = f'http://{proxy}'
    else:
        logger.warning(f"지원하지 않는 프록시 타입: {proxy_type}, 기본값 'socks5' 사용")
        proxy_url = f'socks5://{proxy}'
        proxy_type_lower = 'socks5'
    
    return {
        'proxy': proxy,
        'proxy_type': proxy_type_lower,
        'chrome_option': f'--proxy-server={proxy_url}'
    }


# ============================================================================
# 비동기 프록시 테스트 기능
# ============================================================================

async def test_socks5_proxy(proxy: str, timeout: int = 5) -> Dict:
    """
    SOCKS5 프록시를 테스트합니다.
    
    Args:
        proxy: 프록시 주소 (IP:포트 형식)
        timeout: 타임아웃 (초)
    
    Returns:
        dict: 테스트 결과
            {
                'proxy': 'IP:포트',
                'success': bool,
                'latency': float (ms) 또는 None,
                'error': str 또는 None,
                'actual_ip': str 또는 None
            }
    """
    try:
        import socket
        import socks
    except ImportError:
        return {
            "proxy": proxy,
            "success": False,
            "latency": None,
            "error": "PySocks 모듈이 설치되지 않았습니다. pip install PySocks",
            "actual_ip": None
        }
    
    start_time = time.time()
    ip, port = proxy.split(":")
    port = int(port)
    
    try:
        # SOCKS5 연결 테스트
        s = socks.socksocket()
        s.set_proxy(socks.SOCKS5, ip, port)
        s.settimeout(timeout)
        
        # SOCKS 핸드셰이크 테스트
        s.connect(("api.ipify.org", 80))
        s.close()
    except Exception as e:
        return {
            "proxy": proxy,
            "success": False,
            "latency": None,
            "error": f"SOCKS 연결 실패: {str(e)}",
            "actual_ip": None
        }
    
    # HTTP GET 테스트
    try:
        proxy_url = f"socks5://{proxy}"
        timeout_obj = aiohttp.ClientTimeout(total=timeout)
        
        async with aiohttp.ClientSession(timeout=timeout_obj) as session:
            async with session.get(
                TEST_URL,
                proxy=proxy_url,
                timeout=timeout_obj
            ) as resp:
                if resp.status != 200:
                    return {
                        "proxy": proxy,
                        "success": False,
                        "latency": None,
                        "error": f"HTTP {resp.status}",
                        "actual_ip": None
                    }
                
                result = await resp.json()
                actual_ip = result.get('ip', 'Unknown')
                
                latency = round((time.time() - start_time) * 1000, 2)
                
                return {
                    "proxy": proxy,
                    "success": True,
                    "latency": latency,
                    "actual_ip": actual_ip,
                    "error": None
                }
    
    except asyncio.TimeoutError:
        return {
            "proxy": proxy,
            "success": False,
            "latency": None,
            "error": "Timeout",
            "actual_ip": None
        }
    except Exception as e:
        return {
            "proxy": proxy,
            "success": False,
            "latency": None,
            "error": str(e),
            "actual_ip": None
        }


async def test_http_proxy(proxy: str, timeout: int = 5) -> Dict:
    """
    HTTP 프록시를 테스트합니다.
    
    Args:
        proxy: 프록시 주소 (IP:포트 형식)
        timeout: 타임아웃 (초)
    
    Returns:
        dict: 테스트 결과
            {
                'proxy': 'IP:포트',
                'success': bool,
                'latency': float (ms) 또는 None,
                'error': str 또는 None
            }
    """
    start_time = time.time()
    
    try:
        # HTTP 프록시 URL 형식
        proxy_url = f"http://{proxy}"
        
        # aiohttp를 사용한 프록시 테스트
        timeout_obj = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(timeout=timeout_obj) as session:
            async with session.get(
                TEST_URL,
                proxy=proxy_url,
                timeout=timeout_obj
            ) as resp:
                if resp.status != 200:
                    return {
                        "proxy": proxy,
                        "success": False,
                        "latency": None,
                        "error": f"HTTP {resp.status}"
                    }
                
                # 응답 읽기
                result = await resp.json()
                actual_ip = result.get('ip', 'Unknown')
                
                latency = round((time.time() - start_time) * 1000, 2)
                
                return {
                    "proxy": proxy,
                    "success": True,
                    "latency": latency,
                    "actual_ip": actual_ip,
                    "error": None
                }
    
    except asyncio.TimeoutError:
        return {
            "proxy": proxy,
            "success": False,
            "latency": None,
            "error": "Timeout"
        }
    except Exception as e:
        return {
            "proxy": proxy,
            "success": False,
            "latency": None,
            "error": str(e)
        }


async def test_proxies_parallel(proxy_list: List[str], timeout: int = 5, proxy_type: str = 'http') -> List[Dict]:
    """
    여러 프록시를 병렬로 테스트합니다.
    
    Args:
        proxy_list: 프록시 목록
        timeout: 각 프록시 테스트 타임아웃 (초)
        proxy_type: 프록시 타입 ('http' 또는 'socks5', 기본값: 'http')
    
    Returns:
        List[Dict]: 테스트 결과 목록
    """
    if proxy_type.lower() == 'socks5':
        tasks = [test_socks5_proxy(proxy, timeout) for proxy in proxy_list]
    else:
        tasks = [test_http_proxy(proxy, timeout) for proxy in proxy_list]
    return await asyncio.gather(*tasks)


async def test_proxies_from_file(ip_list_file: str = "iplist.txt", timeout: int = 5, proxy_type: str = 'socks5') -> List[Dict]:
    """
    iplist.txt 파일에서 프록시를 읽어서 테스트합니다.
    
    Args:
        ip_list_file: 프록시 IP 목록 파일 경로
        timeout: 각 프록시 테스트 타임아웃 (초)
        proxy_type: 프록시 타입 ('http' 또는 'socks5', 기본값: 'socks5')
    
    Returns:
        List[Dict]: 테스트 결과 목록
    """
    rotator = ProxyRotator(ip_list_file)
    proxy_list = rotator.get_all_proxies()
    
    if not proxy_list:
        logger.error("테스트할 프록시가 없습니다.")
        return []
    
    logger.info(f"{proxy_type.upper()} 프록시 테스트 시작: {len(proxy_list)}개")
    results = await test_proxies_parallel(proxy_list, timeout, proxy_type)
    return results


# 테스트 코드
if __name__ == "__main__":
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    async def main():
        # ProxyRotator 테스트
        print("=" * 70)
        print("ProxyRotator 테스트")
        print("=" * 70)
        
        rotator = ProxyRotator()
        
        print(f"\n프록시 개수: {rotator.get_proxy_count()}")
        print(f"전체 프록시 목록: {rotator.get_all_proxies()}")
        
        print("\n프록시 순환 테스트 (5번):")
        for i in range(5):
            proxy = rotator.get_next_proxy()
            print(f"  {i+1}. {proxy}")
        
        print("\n특정 인덱스 프록시:")
        for i in range(rotator.get_proxy_count()):
            proxy = rotator.get_proxy_at_index(i)
            print(f"  인덱스 {i}: {proxy}")
        
        print("\nChrome 옵션용 프록시 설정 (SOCKS5):")
        for i in range(3):
            proxy_config = get_proxy_for_chrome_options(proxy_type='socks5')
            print(f"  {i+1}. {proxy_config}")
        
        print("\nChrome 옵션용 프록시 설정 (HTTP):")
        for i in range(3):
            proxy_config = get_proxy_for_chrome_options(proxy_type='http')
            print(f"  {i+1}. {proxy_config}")
        
        # 프록시 테스트 (iplist.txt에서 불러오기)
        print("\n" + "=" * 70)
        print("SOCKS5 프록시 테스트 (iplist.txt에서 불러오기)")
        print("=" * 70)
        
        results = await test_proxies_from_file("iplist.txt", timeout=5, proxy_type='socks5')
        
        # 살아있는 프록시 (응답 빠른 순)
        alive = sorted(
            [r for r in results if r["success"]],
            key=lambda x: x["latency"] if x["latency"] is not None else float('inf')
        )
        
        print("\n=== 사용 가능한 SOCKS5 프록시 (응답 빠른 순) ===")
        if alive:
            for p in alive:
                actual_ip = p.get('actual_ip', 'N/A')
                print(f"  {p['proxy']} - 지연시간: {p['latency']}ms, 실제 IP: {actual_ip}")
        else:
            print("  사용 가능한 프록시가 없습니다.")
        
        # 죽은 프록시
        dead = [r for r in results if not r["success"]]
        print("\n=== 사용 불가능한 SOCKS5 프록시 ===")
        if dead:
            for p in dead:
                error = p.get('error', 'Unknown error')
                print(f"  {p['proxy']} - 오류: {error}")
        else:
            print("  사용 불가능한 프록시가 없습니다.")
        
        print("\n" + "=" * 70)
        print(f"테스트 완료! (총 {len(results)}개 중 {len(alive)}개 사용 가능)")
        print("=" * 70)
    
    # 비동기 메인 함수 실행
    asyncio.run(main())

