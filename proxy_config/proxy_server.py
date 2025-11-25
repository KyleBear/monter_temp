"""
로컬 SOCKS5 프록시 서버 + 화이트리스트 테스터

사용법:
1. 먼저 프록시 서버 실행: python proxy_server.py
2. 다른 터미널에서 테스트: python proxy_server.py --test
"""

import asyncio
import aiohttp
import time
import socks
import socket
import struct
import sys
from threading import Thread

# 프록시 서버 설정
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 1080
PROXY_USERNAME = "monter"
PROXY_PASSWORD = "monter"

# 화이트리스트 IP (이 IP들로만 연결 허용)
WHITELIST_IPS = [
    "119.199.216.6",
    "121.176.22.12",
    "14.43.117.17",
    "175.215.129.13",
    "8.8.8.8",  # 테스트용
]

TEST_URL = "https://api.ipify.org?format=json"


class SOCKS5Server:
    """간단한 SOCKS5 프록시 서버 (화이트리스트 기능 포함)"""
    
    def __init__(self, host, port, username, password, whitelist):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.whitelist = set(whitelist)
        self.server = None
    
    async def handle_client(self, reader, writer):
        """클라이언트 연결 처리"""
        client_addr = writer.get_extra_info('peername')
        try:
            # SOCKS5 핸드셰이크
            data = await reader.read(2)
            if len(data) < 2:
                return
            
            ver, nmethods = struct.unpack('BB', data)
            
            if ver != 5:
                writer.close()
                await writer.wait_closed()
                return
            
            # 인증 방법 읽기
            methods = await reader.read(nmethods)
            if len(methods) < nmethods:
                return
            
            # 사용자명/비밀번호 인증 요구 (0x02)
            writer.write(struct.pack('BB', 5, 2))
            await writer.drain()
            
            # 인증 정보 받기
            auth_header = await reader.read(2)
            if len(auth_header) < 2:
                return
            
            ver, ulen = struct.unpack('BB', auth_header)
            if ver != 1:
                return
            
            username_bytes = await reader.read(ulen)
            if len(username_bytes) < ulen:
                return
            username = username_bytes.decode('utf-8', errors='ignore')
            
            plen_byte = await reader.read(1)
            if len(plen_byte) < 1:
                return
            plen = struct.unpack('B', plen_byte)[0]
            
            password_bytes = await reader.read(plen)
            if len(password_bytes) < plen:
                return
            password = password_bytes.decode('utf-8', errors='ignore')
            
            # 인증 확인
            if username != self.username or password != self.password:
                writer.write(struct.pack('BB', 1, 1))  # 인증 실패
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                print(f"[거부] 인증 실패: {username} from {client_addr}")
                return
            
            # 인증 성공
            writer.write(struct.pack('BB', 1, 0))
            await writer.drain()
            
            # 연결 요청 받기
            request_header = await reader.read(4)
            if len(request_header) < 4:
                return
            
            ver, cmd, rsv, atyp = struct.unpack('BBBB', request_header)
            
            if ver != 5:
                return
            
            # CONNECT 명령만 처리 (0x01)
            if cmd != 1:
                # 지원하지 않는 명령
                writer.write(struct.pack('BBBB', 5, 7, 0, 1) + socket.inet_aton('0.0.0.0') + struct.pack('!H', 0))
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                return
            
            # 주소 타입에 따라 처리
            if atyp == 1:  # IPv4
                addr_bytes = await reader.read(4)
                if len(addr_bytes) < 4:
                    return
                addr = socket.inet_ntoa(addr_bytes)
                target_ip = addr
            elif atyp == 3:  # 도메인
                addr_len_byte = await reader.read(1)
                if len(addr_len_byte) < 1:
                    return
                addr_len = struct.unpack('B', addr_len_byte)[0]
                addr_bytes = await reader.read(addr_len)
                if len(addr_bytes) < addr_len:
                    return
                addr = addr_bytes.decode('utf-8', errors='ignore')
                # 도메인을 IP로 변환
                try:
                    target_ip = socket.gethostbyname(addr)
                except socket.gaierror:
                    target_ip = addr
            elif atyp == 4:  # IPv6 (지원하지 않음)
                writer.write(struct.pack('BBBB', 5, 8, 0, 1) + socket.inet_aton('0.0.0.0') + struct.pack('!H', 0))
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                return
            else:
                writer.close()
                await writer.wait_closed()
                return
            
            # 포트 읽기
            port_bytes = await reader.read(2)
            if len(port_bytes) < 2:
                return
            port = struct.unpack('!H', port_bytes)[0]
            
            # 화이트리스트 확인
            if target_ip not in self.whitelist:
                print(f"[차단] {addr}:{port} ({target_ip}) - 화이트리스트에 없음")
                # 연결 거부 응답 (0x02: 규칙에 의해 연결 거부)
                bind_addr = socket.inet_aton('0.0.0.0')
                writer.write(struct.pack('BBBB', 5, 2, 0, 1) + bind_addr + struct.pack('!H', 0))
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                return
            
            # 목적지 서버 연결
            try:
                remote_reader, remote_writer = await asyncio.wait_for(
                    asyncio.open_connection(addr, port),
                    timeout=10.0
                )
                print(f"[허용] {addr}:{port} ({target_ip})")
                
                # 연결 성공 응답 (0x00: 성공)
                # 바인드 주소는 실제로는 사용하지 않지만, 프로토콜상 필요
                bind_addr = socket.inet_aton('0.0.0.0')
                bind_port = 0
                writer.write(struct.pack('BBBB', 5, 0, 0, 1) + bind_addr + struct.pack('!H', bind_port))
                await writer.drain()
                
                # 양방향 데이터 전달
                try:
                    await asyncio.gather(
                        self.pipe(reader, remote_writer),
                        self.pipe(remote_reader, writer),
                        return_exceptions=True
                    )
                except Exception as pipe_error:
                    print(f"[경고] 데이터 전달 중 오류: {pipe_error}")
                
            except asyncio.TimeoutError:
                print(f"[오류] {addr}:{port} 연결 타임아웃")
                bind_addr = socket.inet_aton('0.0.0.0')
                writer.write(struct.pack('BBBB', 5, 4, 0, 1) + bind_addr + struct.pack('!H', 0))
                await writer.drain()
            except Exception as e:
                print(f"[오류] {addr}:{port} 연결 실패: {e}")
                bind_addr = socket.inet_aton('0.0.0.0')
                writer.write(struct.pack('BBBB', 5, 1, 0, 1) + bind_addr + struct.pack('!H', 0))
                await writer.drain()
            finally:
                try:
                    remote_writer.close()
                    await remote_writer.wait_closed()
                except:
                    pass
            
            writer.close()
            await writer.wait_closed()
            
        except Exception as e:
            print(f"[오류] 클라이언트 처리 중: {e}")
            import traceback
            traceback.print_exc()
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass
    
    async def pipe(self, reader, writer):
        """데이터 전달"""
        try:
            while True:
                data = await reader.read(8192)
                if not data:
                    break
                writer.write(data)
                await writer.drain()
        except:
            pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass
    
    async def start(self):
        """서버 시작"""
        self.server = await asyncio.start_server(
            self.handle_client,
            self.host,
            self.port
        )
        
        print(f"=== SOCKS5 프록시 서버 시작 ===")
        print(f"주소: {self.host}:{self.port}")
        print(f"인증: {self.username} / {self.password}")
        print(f"화이트리스트: {len(self.whitelist)}개 IP")
        print(f"\n허용된 IP:")
        for ip in sorted(self.whitelist):
            print(f"  - {ip}")
        print("\n서버 실행 중... (Ctrl+C로 종료)\n")
        
        async with self.server:
            await self.server.serve_forever()


# ============= 테스트 코드 =============

async def test_proxy():
    """프록시 서버 테스트"""
    print("=== 프록시 서버 테스트 ===\n")
    
    # 1. 화이트리스트 IP 테스트 (도메인으로 테스트)
    print("1. 화이트리스트 IP 테스트")
    test_targets = [
        ("api.ipify.org", "8.8.8.8"),  # 화이트리스트에 있음
        ("1.1.1.1", "1.1.1.1"),  # 화이트리스트에 없음 (차단되어야 함)
    ]
    
    for target_name, expected_ip in test_targets:
        try:
            proxy_url = f"socks5://{PROXY_USERNAME}:{PROXY_PASSWORD}@{PROXY_HOST}:{PROXY_PORT}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    TEST_URL,
                    proxy=proxy_url,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        actual_ip = data.get('ip', 'Unknown')
                        if expected_ip in WHITELIST_IPS:
                            print(f"  [OK] {target_name} -> External IP: {actual_ip}")
                        else:
                            print(f"  [BLOCKED] {target_name} - 화이트리스트에 없어 차단되어야 함")
                    else:
                        print(f"  [FAIL] {target_name}: HTTP {resp.status}")
        except Exception as e:
            error_msg = str(e)
            if "Server disconnected" in error_msg or "Connection refused" in error_msg:
                print(f"  [FAIL] {target_name}: 프록시 서버 연결 실패 - 서버가 실행 중인지 확인하세요")
            else:
                print(f"  [FAIL] {target_name}: {error_msg[:80]}")
    
    print(f"\n현재 공인 IP: 1.242.205.119")
    print("프록시를 통과하면 화이트리스트 IP 중 하나로 나가야 합니다.")
    print(f"\n화이트리스트 IP: {', '.join(WHITELIST_IPS)}")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        # 테스트 모드
        asyncio.run(test_proxy())
    else:
        # 서버 모드
        server = SOCKS5Server(
            PROXY_HOST,
            PROXY_PORT,
            PROXY_USERNAME,
            PROXY_PASSWORD,
            WHITELIST_IPS
        )
        
        try:
            asyncio.run(server.start())
        except KeyboardInterrupt:
            print("\n\n서버 종료")


if __name__ == "__main__":
    # 필요한 패키지: pip install aiohttp pysocks
    main()