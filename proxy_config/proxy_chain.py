"""
프록시 체인 서버: 로컬 SOCKS5 → 화이트리스트 원격 프록시

동작 방식:
[Chrome] → [127.0.0.1:1080] → [화이트리스트 프록시] → [모든 사이트]

사용법:
1. 프록시 서버 실행: python proxy_chain.py
2. Chrome 설정: socks5://127.0.0.1:1080
3. 네이버, 구글 등 모든 사이트 접속 가능
"""

import asyncio
import struct
import socket
import random
from collections import deque
import sys
import os
import subprocess
import platform
# 자동 프록시 구성 스크립트(PAC)
# 자동 감지(WS-Discovery / WPAD)
# 수동 프록시 설정(HTTP/HTTPS/SOCKS) -- 수동 프록시 사용

# 로컬 프록시 서버 설정
LOCAL_PROXY_HOST = "127.0.0.1"
LOCAL_PROXY_PORT = 1080

# 화이트리스트 원격 프록시 (이 프록시들을 통해 나감)
# 호출 ip 에 15 개 정도를 두고 rotating 하기

WHITELIST_PROXIES = [
    # {"host": "119.199.216.6", "port": 1201},
    {"host": "121.176.22.12", "port": 1202},
    {"host": "14.43.117.17", "port": 1203},
    # {"host": "175.215.129.13", "port": 1204},
    # {"host": "183.104.112.7", "port": 1205},
    # {"host": "119.199.216.54", "port": 1206},
    # {"host": "121.176.22.100", "port": 1207},
    # {"host": "221.152.95.23", "port": 1208},
    # {"host": "221.162.180.20", "port": 1209},
    # {"host": "221.162.181.4", "port": 1210},
    # {"host": "121.145.91.135", "port": 1221},
    # {"host": "121.145.93.230", "port": 1222},
    # {"host": "125.134.155.245", "port": 1223},
    ]

# 프록시 선택 전략: "random", "round_robin", "fastest", "sequential"
# PROXY_STRATEGY = "random"
PROXY_STRATEGY = "sequential"

# 프록시 선택 인덱스 (round_robin용)
proxy_index = 0


class ProxyChainServer:
    """로컬 SOCKS5 프록시 → 원격 프록시 체인"""
    
    def __init__(self, host, port, remote_proxies):
        self.host = host
        self.port = port
        self.remote_proxies = remote_proxies
        self.server = None
        # sequential 전략용 초기화 (필수!)
        self.used_proxies = deque()
        self.available_proxies = deque(remote_proxies.copy())
        # 종료 플래그
        self.shutdown_flag = False
        # 프록시 선택 락 (동시성 안전)
        self.proxy_lock = asyncio.Lock()
        # 클라이언트별 프록시 매핑 (같은 클라이언트는 같은 프록시 사용)
        self.client_proxy_map = {}  # client_addr -> proxy
    
    async def select_proxy(self):
        """화이트리스트에서 프록시 선택 (동시성 안전)"""
        async with self.proxy_lock:
            global proxy_index
            
            if PROXY_STRATEGY == "random":
                return random.choice(self.remote_proxies)
            elif PROXY_STRATEGY == "round_robin":
                proxy = self.remote_proxies[proxy_index % len(self.remote_proxies)]
                proxy_index += 1
                return proxy
            elif PROXY_STRATEGY == "sequential":
                # 사용하지 않은 프록시가 있으면 순차적으로 선택
                if self.available_proxies:
                    proxy = self.available_proxies.popleft()
                    self.used_proxies.append(proxy)
                    print(f"[프록시 선택] 프록시 할당: {proxy['host']}:{proxy['port']} (남은 프록시: {len(self.available_proxies)}개)")
                    return proxy
                else:
                    print("[프록시] 모든 프록시 사용 완료, 서버를 종료합니다")
                    raise Exception("모든 프록시를 사용 완료했습니다. 서버를 종료합니다.")
            else:
                return self.remote_proxies[0]
    
    def is_test_selenium_running(self):
        """test_web_selenium.py 프로세스가 실행 중인지 확인"""
        try:
            if platform.system() == 'Windows':
                # Windows: wmic로 정확하게 확인
                result = subprocess.run(
                    ['wmic', 'process', 'where', 'name="python.exe"', 'get', 'processid,commandline', '/format:list'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    # CommandLine에 test_web_selenium.py가 포함되어 있는지 확인
                    if 'test_web_selenium.py' in result.stdout:
                        return True
            else:
                # Linux/Mac: ps로 프로세스 확인
                result = subprocess.run(
                    ['ps', 'aux'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    return 'test_web_selenium.py' in result.stdout
            
            return False
        except Exception as e:
            print(f"[프로세스 확인] 오류: {e}")
            return False
    
    async def wait_for_test_selenium_completion(self, max_wait_seconds=600):
        """test_web_selenium.py가 종료될 때까지 대기"""
        print(f"[대기] test_web_selenium.py 종료 대기 중... (최대 {max_wait_seconds}초)")
        
        start_time = asyncio.get_event_loop().time()
        check_interval = 2  # 2초마다 확인
        
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            
            if elapsed >= max_wait_seconds:
                print(f"[대기] 최대 대기 시간({max_wait_seconds}초) 초과, 종료합니다")
                break
            
            if not self.is_test_selenium_running():
                print(f"[대기] test_web_selenium.py 종료 확인 (대기 시간: {elapsed:.1f}초)")
                break
            
            # 진행 상황 출력 (30초마다)
            if int(elapsed) % 30 == 0 and int(elapsed) > 0:
                print(f"[대기] test_web_selenium.py 실행 중... (경과: {int(elapsed)}초)")
            
            await asyncio.sleep(check_interval)
    
    async def connect_to_remote_proxy(self, proxy, target_host, target_port, proxy_type='socks5'):
        """원격 프록시에 연결 (SOCKS5 또는 HTTP)"""
        try:
            # 원격 프록시에 연결 (타임아웃 설정)
            print(f"[디버그] 원격 프록시 연결 시도 ({proxy_type}): {proxy['host']}:{proxy['port']}")
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(proxy['host'], proxy['port']),
                timeout=10.0
            )
            print(f"[디버그] 원격 프록시 연결 성공: {proxy['host']}:{proxy['port']}")
            
            if proxy_type == 'http':
                # HTTP CONNECT 프록시
                return await self.connect_http_proxy(reader, writer, target_host, target_port, proxy)
            else:
                # SOCKS5 프록시
                return await self.connect_socks5_proxy(reader, writer, target_host, target_port, proxy)
                
        except asyncio.TimeoutError:
            raise Exception(f"타임아웃: {proxy['host']}:{proxy['port']}에 연결할 수 없습니다")
        except ConnectionRefusedError:
            raise Exception(f"연결 거부: {proxy['host']}:{proxy['port']}가 응답하지 않습니다")
        except Exception as e:
            print(f"[디버그] 원격 프록시 연결 오류: {e}")
            raise Exception(f"원격 프록시 연결 실패 ({proxy['host']}:{proxy['port']}): {e}")
    
    async def connect_socks5_proxy(self, reader, writer, target_host, target_port, proxy):
        """SOCKS5 프록시 연결"""
        try:
            # SOCKS5 핸드셰이크
            # 1. 인증 방법 협상 (인증 없음: 0x00)
            writer.write(struct.pack('BBB', 5, 1, 0))
            await asyncio.wait_for(writer.drain(), timeout=5.0)
            
            response = await asyncio.wait_for(reader.read(2), timeout=10.0)  # 타임아웃 증가
            if len(response) < 2:
                raise Exception("프록시 서버 응답 없음 (SOCKS5 핸드셰이크 실패)")
            
            ver, method = struct.unpack('BB', response)
            print(f"[디버그] 원격 프록시 응답: 버전={ver}, 방법={method}")
            
            if ver != 5:
                raise Exception(f"잘못된 SOCKS 버전: {ver} (HTTP 프록시일 수 있음)")
            if method != 0:
                raise Exception(f"인증 필요 또는 지원하지 않는 방법: {method}")
            
            # 2. 연결 요청
            # 도메인 타입 (0x03)
            target_host_bytes = target_host.encode()
            host_len = len(target_host_bytes)
            
            request = struct.pack('BBBB', 5, 1, 0, 3)  # VER, CMD, RSV, ATYP
            request += struct.pack('B', host_len) + target_host_bytes
            request += struct.pack('!H', target_port)
            
            writer.write(request)
            await writer.drain()
            
            # 3. 응답 받기
            response = await asyncio.wait_for(reader.read(4), timeout=5.0)
            if len(response) < 4:
                raise Exception("원격 프록시 응답 불완전")
            
            ver, rep, rsv, atyp = struct.unpack('BBBB', response)
            print(f"[디버그] 원격 프록시 연결 응답: 버전={ver}, 응답코드={rep}, 주소타입={atyp}")
            
            if atyp == 1:  # IPv4
                bind_addr = await asyncio.wait_for(reader.read(4), timeout=2.0)
            elif atyp == 3:  # 도메인
                addr_len = struct.unpack('B', await asyncio.wait_for(reader.read(1), timeout=2.0))[0]
                bind_addr = await asyncio.wait_for(reader.read(addr_len), timeout=2.0)
            elif atyp == 4:  # IPv6
                bind_addr = await asyncio.wait_for(reader.read(16), timeout=2.0)
            else:
                raise Exception(f"알 수 없는 주소 타입: {atyp}")
            
            bind_port_data = await asyncio.wait_for(reader.read(2), timeout=2.0)  # 포트
            
            # SOCKS5 응답 코드 확인
            if rep != 0:
                error_messages = {
                    1: "일반 SOCKS 서버 오류",
                    2: "연결 규칙에 의해 허용되지 않음",
                    3: "네트워크에 연결할 수 없음",
                    4: "호스트에 연결할 수 없음",
                    5: "연결 거부",
                    6: "TTL 만료",
                    7: "지원하지 않는 명령",
                    8: "지원하지 않는 주소 타입"
                }
                error_msg = error_messages.get(rep, f"알 수 없는 오류 (코드: {rep})")
                raise Exception(f"원격 프록시 연결 거부: {error_msg} (코드: {rep})")
            
            print(f"[디버그] 원격 프록시 연결 성공: {target_host}:{target_port}")
            
            return reader, writer
            
        except Exception as e:
            raise Exception(f"SOCKS5 연결 실패: {e}")
    
    async def connect_http_proxy(self, reader, writer, target_host, target_port, proxy):
        """HTTP CONNECT 프록시 연결"""
        try:
            # HTTP CONNECT 요청
            connect_request = f"CONNECT {target_host}:{target_port} HTTP/1.1\r\n"
            connect_request += f"Host: {target_host}:{target_port}\r\n"
            connect_request += "Proxy-Connection: keep-alive\r\n"
            connect_request += "\r\n"
            
            writer.write(connect_request.encode())
            await asyncio.wait_for(writer.drain(), timeout=5.0)
            
            # 응답 읽기
            response_lines = []
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=10.0)
                if not line:
                    raise Exception("HTTP 프록시 응답 없음")
                
                line_str = line.decode('utf-8', errors='ignore').strip()
                response_lines.append(line_str)
                
                if not line_str:  # 빈 줄 = 헤더 끝
                    break
            
            if not response_lines:
                raise Exception("HTTP 프록시 응답 없음")
            
            status_line = response_lines[0]
            print(f"[디버그] HTTP 프록시 응답: {status_line}")
            
            if not status_line.startswith('HTTP/1.') or '200' not in status_line:
                raise Exception(f"HTTP 프록시 연결 실패: {status_line}")
            
            print(f"[디버그] HTTP 프록시 연결 성공: {target_host}:{target_port}")
            return reader, writer
            
        except Exception as e:
            raise Exception(f"HTTP 프록시 연결 실패: {e}")
    
    async def handle_client(self, client_reader, client_writer):
        """클라이언트 요청 처리"""
        client_addr = client_writer.get_extra_info('peername')
        print(f"[디버그] 클라이언트 연결 시도: {client_addr}")
        
        # 종료 플래그 확인
        if self.shutdown_flag:
            print(f"[종료] 새로운 연결 거부 (모든 프록시 사용 완료)")
            client_writer.write(struct.pack('BBBBIH', 5, 1, 0, 1, 0, 0))
            await client_writer.drain()
            client_writer.close()
            await client_writer.wait_closed()
            return
        
        remote_writer = None
        
        try:
            # 첫 바이트 확인 (SOCKS5 또는 HTTP CONNECT)
            peek_data = await client_reader.read(1)
            if not peek_data:
                print("[디버그] 데이터 없음, 연결 종료")
                return
            
            first_byte = peek_data[0]
            print(f"[디버그] 첫 바이트: {first_byte} (0x{first_byte:02x})")
            
            # HTTP CONNECT 요청인지 확인 (첫 바이트가 'C' 또는 'G' 등)
            if first_byte in [ord('C'), ord('G'), ord('P'), ord('D'), ord('H'), ord('O'), ord('T')]:
                # HTTP 프록시로 처리
                await self.handle_http_proxy(client_reader, client_writer, peek_data)
                return
            
            # SOCKS5 처리
            if first_byte != 5:
                print(f"[디버그] SOCKS5가 아님 (버전: {first_byte}), 연결 종료")
                client_writer.close()
                await client_writer.wait_closed()
                return
            
            # 나머지 바이트 읽기
            second_byte = await client_reader.read(1)
            if not second_byte:
                print("[디버그] 두 번째 바이트 없음, 연결 종료")
                return
            
            nmethods = second_byte[0]
            print(f"[디버그] SOCKS5 버전: 5, 인증 방법 수: {nmethods}")
            
            # 인증 방법 읽기
            methods = await client_reader.read(nmethods)
            
            # 인증 없음 (0x00) 응답
            client_writer.write(struct.pack('BB', 5, 0))
            await client_writer.drain()
            
            # 연결 요청 받기
            data = await client_reader.read(4)
            ver, cmd, rsv, atyp = struct.unpack('BBBB', data)
            
            # 목적지 주소 파싱
            if atyp == 1:  # IPv4
                addr = socket.inet_ntoa(await client_reader.read(4))
            elif atyp == 3:  # 도메인
                addr_len = struct.unpack('B', await client_reader.read(1))[0]
                addr = (await client_reader.read(addr_len)).decode()
            elif atyp == 4:  # IPv6
                addr = socket.inet_ntop(socket.AF_INET6, await client_reader.read(16))
            else:
                client_writer.close()
                await client_writer.wait_closed()
                return
            
            port = struct.unpack('!H', await client_reader.read(2))[0]
            
            # 화이트리스트 프록시 선택
            # 같은 클라이언트 IP의 모든 연결은 같은 프록시 사용 (같은 반복의 Chrome 인스턴스)
            try:
                # 클라이언트 IP 주소만 사용 (포트는 제외 - 같은 IP의 모든 연결이 같은 프록시 사용)
                client_ip = client_addr[0] if isinstance(client_addr, tuple) else str(client_addr).split(':')[0]
                
                # 같은 IP가 이미 프록시를 할당받았으면 재사용
                if client_ip in self.client_proxy_map:
                    selected_proxy = self.client_proxy_map[client_ip]
                    print(f"[프록시 재사용] {client_ip} → 프록시: {selected_proxy['host']}:{selected_proxy['port']}")
                else:
                    # 새로운 프록시 할당
                    selected_proxy = await self.select_proxy()
                    self.client_proxy_map[client_ip] = selected_proxy
                    print(f"[프록시 할당] {client_ip} → 프록시: {selected_proxy['host']}:{selected_proxy['port']}")
            except Exception as e:
                if "모든 프록시를 사용 완료" in str(e):
                    print(f"[종료] {str(e)}")
                    client_writer.write(struct.pack('BBBBIH', 5, 1, 0, 1, 0, 0))
                    await client_writer.drain()
                    client_writer.close()
                    await client_writer.wait_closed()
                    
                    # 새로운 연결 거부 플래그 설정
                    self.shutdown_flag = True
                    
                    # test_web_selenium.py가 종료될 때까지 대기
                    await self.wait_for_test_selenium_completion(max_wait_seconds=600)
                    
                    # 서버 및 프로세스 종료
                    if self.server:
                        print("[서버] 프록시 서버 종료 중...")
                        self.server.close()
                        await self.server.wait_closed()
                    print("[프로세스] 모든 프록시 사용 완료 및 test_web_selenium.py 종료 확인, proxy_chain.py 종료")
                    import os
                    os._exit(0)
                else:
                    raise
            
            print(f"[연결] {addr}:{port} → 프록시: {selected_proxy['host']}:{selected_proxy['port']}")
            
            # 원격 프록시를 통해 연결 (재시도 로직)
            max_retries = len(self.remote_proxies)
            last_error = None
            success = False
            
            for attempt in range(max_retries):
                try:
                    print(f"[시도 {attempt+1}/{max_retries}] {addr}:{port} → {selected_proxy['host']}:{selected_proxy['port']}")
                    
                    # 먼저 SOCKS5로 시도, 실패하면 HTTP로 시도
                    proxy_types = ['socks5', 'http']
                    last_error = None
                    
                    for proxy_type in proxy_types:
                        try:
                            remote_reader, remote_writer = await self.connect_to_remote_proxy(
                                selected_proxy, 
                                addr, 
                                port,
                                proxy_type=proxy_type
                            )
                            break  # 성공 시 루프 종료
                        except Exception as e:
                            last_error = e
                            if proxy_type == 'socks5':
                                print(f"[시도] SOCKS5 실패, HTTP로 재시도: {str(e)[:100]}")
                                continue
                            else:
                                raise  # HTTP도 실패하면 예외 발생
                    
                    # 클라이언트에게 성공 응답
                    client_writer.write(struct.pack('BBBBIH', 5, 0, 0, 1, 0, 0))
                    await client_writer.drain()
                    
                    print(f"[성공] {addr}:{port} → 프록시: {selected_proxy['host']}:{selected_proxy['port']}")
                    
                    # 양방향 데이터 전달
                    await asyncio.gather(
                        self.pipe(client_reader, remote_writer, f"{addr}:{port} → 원격"),
                        self.pipe(remote_reader, client_writer, f"원격 → {addr}:{port}")
                    )
                    success = True
                    break  # 성공 시 루프 종료
                    
                except Exception as e:
                    last_error = e
                    print(f"[실패 {attempt+1}] {selected_proxy['host']}:{selected_proxy['port']} - {str(e)}")
                    import traceback
                    traceback.print_exc()
                    
                    # sequential이 아니고 다음 프록시가 있으면 재시도
                    if PROXY_STRATEGY != "sequential" and attempt < max_retries - 1:
                        try:
                            selected_proxy = await self.select_proxy()
                            print(f"[재시도] 다음 프록시로 시도: {selected_proxy['host']}:{selected_proxy['port']}")
                        except:
                            break
                    else:
                        break  # sequential이면 한 번만 시도
            
            if not success:
                print(f"[최종 실패] {addr}:{port} - 모든 프록시 시도 실패: {last_error}")
                # 연결 실패 응답
                client_writer.write(struct.pack('BBBBIH', 5, 1, 0, 1, 0, 0))
                await client_writer.drain()
            
        except Exception as e:
            print(f"[오류] 클라이언트 처리 중: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            try:
                if remote_writer:
                    remote_writer.close()
                    await remote_writer.wait_closed()
            except:
                pass
            
            try:
                client_writer.close()
                await client_writer.wait_closed()
            except:
                pass
    
    async def handle_http_proxy(self, client_reader, client_writer, first_byte):
        """HTTP CONNECT 프록시 처리"""
        try:
            # 첫 바이트를 포함한 전체 요청 읽기
            buffer = first_byte
            request_lines = []
            line = b""
            
            # HTTP 요청 헤더 읽기
            while True:
                chunk = await client_reader.read(1)
                if not chunk:
                    break
                buffer += chunk
                line += chunk
                
                if chunk == b'\n':
                    line_str = line.decode('utf-8', errors='ignore').strip()
                    request_lines.append(line_str)
                    if not line_str:  # 빈 줄 = 헤더 끝
                        break
                    line = b""
            
            request_text = buffer.decode('utf-8', errors='ignore')
            print(f"[HTTP] 요청: {request_text[:200]}")
            
            # CONNECT 요청 파싱
            if not request_lines:
                raise Exception("HTTP 요청 파싱 실패")
            
            first_line = request_lines[0]
            if not first_line.startswith('CONNECT'):
                raise Exception(f"HTTP CONNECT가 아님: {first_line}")
            
            # CONNECT example.com:443 HTTP/1.1 형식 파싱
            parts = first_line.split()
            if len(parts) < 2:
                raise Exception(f"잘못된 CONNECT 요청: {first_line}")
            
            target = parts[1]  # example.com:443
            if ':' in target:
                addr, port_str = target.rsplit(':', 1)
                port = int(port_str)
            else:
                addr = target
                port = 443  # 기본 HTTPS 포트
            
            print(f"[HTTP CONNECT] {addr}:{port}")
            
            # 화이트리스트 프록시 선택
            # 같은 클라이언트 IP의 모든 연결은 같은 프록시 사용 (같은 반복의 Chrome 인스턴스)
            try:
                # 클라이언트 IP 주소만 사용 (포트는 제외 - 같은 IP의 모든 연결이 같은 프록시 사용)
                client_addr = client_writer.get_extra_info('peername')
                client_ip = client_addr[0] if isinstance(client_addr, tuple) else str(client_addr).split(':')[0]
                
                # 같은 IP가 이미 프록시를 할당받았으면 재사용
                if client_ip in self.client_proxy_map:
                    selected_proxy = self.client_proxy_map[client_ip]
                    print(f"[프록시 재사용] {client_ip} → 프록시: {selected_proxy['host']}:{selected_proxy['port']}")
                else:
                    # 새로운 프록시 할당
                    selected_proxy = await self.select_proxy()
                    self.client_proxy_map[client_ip] = selected_proxy
                    print(f"[프록시 할당] {client_ip} → 프록시: {selected_proxy['host']}:{selected_proxy['port']}")
            except Exception as e:
                if "모든 프록시를 사용 완료" in str(e):
                    print(f"[종료] {str(e)}")
                    client_writer.write(b"HTTP/1.1 503 Service Unavailable\r\n\r\n")
                    await client_writer.drain()
                    client_writer.close()
                    await client_writer.wait_closed()
                    
                    # 새로운 연결 거부 플래그 설정
                    self.shutdown_flag = True
                    
                    # test_web_selenium.py가 종료될 때까지 대기
                    await self.wait_for_test_selenium_completion(max_wait_seconds=600)
                    
                    if self.server:
                        print("[서버] 프록시 서버 종료 중...")
                        self.server.close()
                        await self.server.wait_closed()
                    print("[프로세스] 모든 프록시 사용 완료 및 test_web_selenium.py 종료 확인, proxy_chain.py 종료")
                    import os
                    os._exit(0)
                else:
                    raise
            
            # 원격 SOCKS5 프록시를 통해 연결
            try:
                remote_reader, remote_writer = await self.connect_to_remote_proxy(
                    selected_proxy,
                    addr,
                    port
                )
                
                # HTTP 200 OK 응답
                client_writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                await client_writer.drain()
                
                print(f"[HTTP 성공] {addr}:{port} → 프록시: {selected_proxy['host']}:{selected_proxy['port']}")
                
                # 양방향 데이터 전달
                await asyncio.gather(
                    self.pipe(client_reader, remote_writer, f"{addr}:{port} → 원격"),
                    self.pipe(remote_reader, client_writer, f"원격 → {addr}:{port}")
                )
                
            except Exception as e:
                print(f"[HTTP 오류] {addr}:{port} - {str(e)}")
                import traceback
                traceback.print_exc()
                # 연결 실패 응답
                client_writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                await client_writer.drain()
                
        except Exception as e:
            print(f"[HTTP 오류] 클라이언트 처리 중: {e}")
            import traceback
            traceback.print_exc()
        finally:
            try:
                client_writer.close()
                await client_writer.wait_closed()
            except:
                pass
    
    async def pipe(self, reader, writer, label=""):
        """데이터 전달"""
        try:
            while True:
                data = await reader.read(8192)
                if not data:
                    break
                writer.write(data)
                await writer.drain()
        except Exception as e:
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
        
        print(f"=== 프록시 체인 서버 시작 ===")
        print(f"로컬 주소: {self.host}:{self.port}")
        print(f"프록시 전략: {PROXY_STRATEGY}")
        print(f"\n화이트리스트 프록시 ({len(self.remote_proxies)}개):")
        for i, proxy in enumerate(self.remote_proxies, 1):
            print(f"  {i}. {proxy['host']}:{proxy['port']}")
        print(f"\nChrome 설정: socks5://{self.host}:{self.port}")
        print("서버 실행 중... (Ctrl+C로 종료)\n")
        
        async with self.server:
            await self.server.serve_forever()


def main():
    server = ProxyChainServer(
        LOCAL_PROXY_HOST,
        LOCAL_PROXY_PORT,
        WHITELIST_PROXIES
    )
    
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print("\n\n서버 종료")


if __name__ == "__main__":
    main()