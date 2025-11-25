import asyncio
import aiohttp
import time
import socket
import socks

TEST_URL = "https://api.ipify.org?format=json"

# SOCKS 테스트 함수
async def test_socks(proxy):
    ip, port = proxy.split(":")
    port = int(port)

    start_time = time.time()

    try:
        # socks 세션 생성
        s = socks.socksocket()
        s.set_proxy(socks.SOCKS5, ip, port)
        s.settimeout(3)

        # SOCKS 핸드셰이크 테스트
        s.connect(("api.ipify.org", 80))
        s.close()
    except Exception:
        return {"proxy": proxy, "success": False, "latency": None}

    # HTTP GET 테스트
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                TEST_URL,
                proxy=f"socks5://{proxy}",
                timeout=3
            ) as resp:
                if resp.status != 200:
                    return {"proxy": proxy, "success": False, "latency": None}

                _ = await resp.text()

        latency = round((time.time() - start_time) * 1000, 2)

        return {"proxy": proxy, "success": True, "latency": latency}

    except Exception:
        return {"proxy": proxy, "success": False, "latency": None}


# 병렬 테스트 실행
async def run_tests(proxy_list):
    tasks = [test_socks(proxy) for proxy in proxy_list]
    return await asyncio.gather(*tasks)


# 실행
if __name__ == "__main__":
    proxies = [
        "1.1.1.1:1080",
        "2.2.2.2:1080",
        "3.3.3.3:1080",
        # ... 100개까지
    ]

    results = asyncio.run(run_tests(proxies))

    alive = sorted(
        [r for r in results if r["success"]],
        key=lambda x: x["latency"]
    )

    print("\n=== 사용 가능한 프록시 (응답 빠른 순) ===")
    for p in alive:
        print(p)

    print("\n=== 죽은 프록시 ===")
    for p in results:
        if not p["success"]:
            print(p["proxy"])

# 100개 SOCKS 서버 동시에 테스트 (asyncio)

# SOCKS 연결 성공 여부 확인

# 실제 HTTP GET 요청 성공 여부 확인

# latency(응답속도) 측정 → 빠른 순 정렬

# 살아있는 프록시만 출력

# === 사용 가능한 프록시 (응답 빠른 순) ===
# {'proxy': '3.3.3.3:1080', 'success': True, 'latency': 182}
# {'proxy': '7.7.7.7:1080', 'success': True, 'latency': 220}
# {'proxy': '5.5.5.5:1080', 'success': True, 'latency': 351}

# === 죽은 프록시 ===
# 1.1.1.1:1080
# 2.2.2.2:1080
# 4.4.4.4:1080