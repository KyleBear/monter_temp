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
        ("59.11.87.11", 1202),
        ("14.35.254.13", 1203),
        ("221.153.232.136", 1204),
        ("222.121.85.3", 1205),
        ("59.12.205.71", 1206),
        ("221.163.198.143", 1207),
    ]
    for host, port in proxies:
        await test_proxy(host, port)

asyncio.run(main())