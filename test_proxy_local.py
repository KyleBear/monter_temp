"""
프록시 로컬 테스트 스크립트
proxy_chain.py를 통해 프록시 연결 테스트
"""

import requests
import socket
import socks
import time
from urllib.parse import urlparse

# 프록시 설정
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 1080
PROXY_URL = f"socks5://{PROXY_HOST}:{PROXY_PORT}"

def test_with_requests():
    """requests 라이브러리로 프록시 테스트"""
    print("=" * 60)
    print("requests 라이브러리로 프록시 테스트")
    print("=" * 60)
    
    proxies = {
        'http': PROXY_URL,
        'https': PROXY_URL
    }
    
    test_urls = [
        'https://www.naver.com',
        'https://www.google.com',
        'https://httpbin.org/ip',  # IP 확인용
    ]
    
    for url in test_urls:
        try:
            print(f"\n[테스트] {url}")
            start_time = time.time()
            response = requests.get(url, proxies=proxies, timeout=10)
            elapsed = time.time() - start_time
            
            print(f"  [OK] 성공! 상태 코드: {response.status_code}")
            print(f"  [OK] 응답 시간: {elapsed:.2f}초")
            
            if 'httpbin.org/ip' in url:
                print(f"  [OK] 외부 IP: {response.json()}")
            
        except requests.exceptions.ProxyError as e:
            print(f"  [FAIL] 프록시 오류: {e}")
        except requests.exceptions.Timeout:
            print(f"  [FAIL] 타임아웃")
        except Exception as e:
            print(f"  [FAIL] 오류: {e}")

def test_with_socks():
    """PySocks를 사용한 직접 소켓 테스트"""
    print("\n" + "=" * 60)
    print("PySocks를 사용한 직접 소켓 테스트")
    print("=" * 60)
    
    try:
        # SOCKS5 프록시 설정
        socks.set_default_proxy(socks.SOCKS5, PROXY_HOST, PROXY_PORT)
        socket.socket = socks.socksocket
        
        print("\n[테스트] 네이버 연결")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect(('www.naver.com', 443))
            print("  [OK] 네이버 연결 성공!")
            sock.close()
        except Exception as e:
            print(f"  [FAIL] 네이버 연결 실패: {e}")
        
        print("\n[테스트] 구글 연결")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect(('www.google.com', 443))
            print("  [OK] 구글 연결 성공!")
            sock.close()
        except Exception as e:
            print(f"  [FAIL] 구글 연결 실패: {e}")
        
        # 프록시 설정 해제
        socks.set_default_proxy()
        socket.socket = socket._socket
        
    except ImportError:
        print("  [FAIL] PySocks가 설치되지 않았습니다. pip install pysocks")

def test_proxy_chain_connection():
    """proxy_chain.py 서버 연결 테스트"""
    print("\n" + "=" * 60)
    print("proxy_chain.py 서버 연결 테스트")
    print("=" * 60)
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((PROXY_HOST, PROXY_PORT))
        sock.close()
        
        if result == 0:
            print(f"  [OK] 프록시 서버 연결 성공: {PROXY_HOST}:{PROXY_PORT}")
        else:
            print(f"  [FAIL] 프록시 서버 연결 실패: {PROXY_HOST}:{PROXY_PORT}")
            print("     proxy_chain.py가 실행 중인지 확인하세요.")
    except Exception as e:
        print(f"  [FAIL] 연결 테스트 오류: {e}")

def test_with_http_proxy():
    """HTTP 프록시로 테스트 (HTTP CONNECT)"""
    print("\n" + "=" * 60)
    print("HTTP 프록시 (CONNECT) 테스트")
    print("=" * 60)
    
    # requests에서 HTTP 프록시는 http:// 형식 사용
    proxies = {
        'http': f'http://{PROXY_HOST}:{PROXY_PORT}',
        'https': f'http://{PROXY_HOST}:{PROXY_PORT}'
    }
    
    # requests의 HTTPAdapter를 사용하여 HTTP CONNECT 지원
    from requests.adapters import HTTPAdapter
    from urllib3.util.connection import create_connection
    
    class SOCKSHTTPAdapter(HTTPAdapter):
        def init_poolmanager(self, *args, **kwargs):
            # SOCKS 프록시를 사용하도록 설정
            kwargs['proxy_url'] = f'socks5://{PROXY_HOST}:{PROXY_PORT}'
            return super().init_poolmanager(*args, **kwargs)
    
    test_urls = [
        'https://www.naver.com',
        'https://httpbin.org/ip',
    ]
    
    # HTTP CONNECT는 requests에서 직접 지원하지 않으므로
    # SOCKS5를 사용하거나 직접 소켓으로 구현해야 함
    print("\n[참고] HTTP CONNECT는 requests에서 직접 지원하지 않습니다.")
    print("      SOCKS5 프록시를 사용하거나 직접 소켓으로 구현해야 합니다.")
    print("      위의 SOCKS5 테스트를 참고하세요.")

def main():
    print("\n" + "=" * 60)
    print("프록시 로컬 테스트 시작")
    print("=" * 60)
    print(f"\n프록시 서버: {PROXY_URL}")
    print("주의: proxy_chain.py가 실행 중이어야 합니다.\n")
    
    # 1. 프록시 서버 연결 확인
    test_proxy_chain_connection()
    
    # 2. SOCKS5 프록시 테스트
    test_with_requests()
    
    # 3. PySocks 직접 테스트
    test_with_socks()
    
    # 4. HTTP 프록시 테스트
    test_with_http_proxy()
    
    print("\n" + "=" * 60)
    print("테스트 완료")
    print("=" * 60)

if __name__ == "__main__":
    main()

