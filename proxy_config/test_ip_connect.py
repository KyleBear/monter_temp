# test_proxy_connection.py
import asyncio
import struct
import socket

async def test_proxy(host, port):
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=5.0
        )
        print(f"✓ {host}:{port} - 연결 성공")
        writer.close()
        await writer.wait_closed()
        return True
    except Exception as e:
        print(f"✗ {host}:{port} - 실패: {e}")
        return False

async def main():
    proxies = [
        ("119.199.216.6", 1202),
        ("121.176.22.12", 1202),
        ("14.43.117.17", 1203),
        ("175.215.129.13", 1204),
        ("183.104.112.7", 1205),
        ("119.199.216.54", 1206),
        ("121.176.22.100", 1207),
        ("221.152.95.23", 1208),
        ("221.162.180.20", 1209),
        ("221.162.181.4", 1210),
        ("121.145.91.135", 1221),
        ("121.145.93.230", 1222),
        ("125.134.155.245", 1223),
        ("125.134.158.129", 1224),
        ("125.134.166.240", 1225),
        ("125.134.189.249", 1226),
    ]
    for host, port in proxies:
        await test_proxy(host, port)

asyncio.run(main())