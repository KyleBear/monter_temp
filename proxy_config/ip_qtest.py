import asyncio
import aiohttp
import time
import socks

# 프록시 설정
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 1080
# PROXY_USERNAME = "monter"
# PROXY_PASSWORD = "monter"

# 화이트리스트 IP (이 IP들로만 프록시를 통해 접속)
WHITELIST_IPS = [
    "119.199.216.6:1201",
    "121.176.22.12:1202",
    "14.43.117.17:1203"
    "121.177.98.230:1245"
    "125.134.205.112:1238"
    "125.135.222.57:1239"
    "175.199.117.118:1240"
    "183.104.81.180:1241"
    "210.113.146.30:1242"
    # 테스트할 IP 추가
]

TEST_URL = "https://api.ipify.org?format=json"


async def test_whitelist_ip(target_ip):
    """화이트리스트 IP로 프록시 연결 테스트"""
    start_time = time.time()
    
    # SOCKS 핸드셰이크 테스트
    try:
        s = socks.socksocket()
        s.set_proxy(
            socks.SOCKS5, 
            PROXY_HOST, 
            PROXY_PORT,
            # username=PROXY_USERNAME,
            # password=PROXY_PASSWORD
        )
        s.settimeout(3)
        
        # 타겟 IP의 HTTP 포트로 연결 시도
        s.connect((target_ip, 80))
        s.close()
    except Exception as e:
        return {
            "target_ip": target_ip,
            "success": False,
            "latency": None,
            "error": str(e)
        }
    
    # HTTP GET 테스트 (프록시 통과 확인)
    try:
        proxy_url = f"socks5://{PROXY_USERNAME}:{PROXY_PASSWORD}@{PROXY_HOST}:{PROXY_PORT}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                TEST_URL,
                proxy=proxy_url,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status != 200:
                    return {
                        "target_ip": target_ip,
                        "success": False,
                        "latency": None,
                        "error": f"HTTP {resp.status}"
                    }
                
                data = await resp.json()
                external_ip = data.get('ip')
        
        latency = round((time.time() - start_time) * 1000, 2)
        
        return {
            "target_ip": target_ip,
            "success": True,
            "latency": latency,
            "external_ip": external_ip,
            "error": None
        }
    
    except asyncio.TimeoutError:
        return {
            "target_ip": target_ip,
            "success": False,
            "latency": None,
            "error": "Timeout"
        }
    except Exception as e:
        return {
            "target_ip": target_ip,
            "success": False,
            "latency": None,
            "error": str(e)
        }


async def run_whitelist_tests(ip_list):
    """화이트리스트 IP들 병렬 테스트"""
    tasks = [test_whitelist_ip(ip) for ip in ip_list]
    return await asyncio.gather(*tasks)


def main():
    print(f"=== 화이트리스트 IP 프록시 테스트 ===")
    print(f"로컬 프록시: {PROXY_HOST}:{PROXY_PORT}")
    print(f"테스트 대상: {len(WHITELIST_IPS)}개 IP\n")
    
    results = asyncio.run(run_whitelist_tests(WHITELIST_IPS))
    
    # 성공한 IP들 (응답 빠른 순 정렬)
    alive = sorted(
        [r for r in results if r["success"]],
        key=lambda x: x["latency"]
    )
    
    print("\n=== 사용 가능한 화이트리스트 IP (응답 빠른 순) ===")
    for p in alive:
        print(f"IP: {p['target_ip']:<15} | Latency: {p['latency']}ms | External IP: {p['external_ip']}")
    
    # 실패한 IP들
    dead = [r for r in results if not r["success"]]
    if dead:
        print("\n=== 연결 실패 IP ===")
        for p in dead:
            print(f"IP: {p['target_ip']:<15} | Error: {p['error']}")
    
    print(f"\n=== 요약 ===")
    print(f"성공: {len(alive)}개 / 실패: {len(dead)}개 / 전체: {len(results)}개")


if __name__ == "__main__":
    # 필요한 패키지: pip install aiohttp pysocks
    main()