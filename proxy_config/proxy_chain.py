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

# 자동 프록시 구성 스크립트(PAC)
# 자동 감지(WS-Discovery / WPAD)
# 수동 프록시 설정(HTTP/HTTPS/SOCKS)

# 로컬 프록시 서버 설정
LOCAL_PROXY_HOST = "127.0.0.1"
LOCAL_PROXY_PORT = 1080

# 화이트리스트 원격 프록시 (이 프록시들을 통해 나감)
WHITELIST_PROXIES = [
    {"host": "9119.199.216.6", "port": 1201},
    {"host": "121.176.22.12", "port": 1202},
    {"host": "14.43.117.17", "port": 1203},
    {"host": "175.215.129.13", "port": 1204},
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
    
    def select_proxy(self):
        """화이트리스트에서 프록시 선택"""
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
                return proxy
            else:
                print("[프록시] 모든 프록시 사용 완료, 서버를 종료합니다")
                if self.server:
                    # 서버 종료를 위한 태스크 생성
                    asyncio.create_task(self._shutdown_server())
                raise Exception("모든 프록시를 사용 완료했습니다. 서버를 종료합니다.")

                # 모든 프록시를 사용했으면 리셋
                # print("[프록시] 모든 프록시 사용 완료, 리셋합니다")
                # self.available_proxies = deque(self.remote_proxies.copy())
                # self.used_proxies.clear()
                # proxy = self.available_proxies.popleft()
                # self.used_proxies.append(proxy)
                # return proxy
        else:
            return self.remote_proxies[0]
    
    async def connect_to_remote_proxy(self, proxy, target_host, target_port):
        """원격 SOCKS5 프록시에 연결"""
        try:
            # 원격 프록시에 연결
            reader, writer = await asyncio.open_connection(
                proxy['host'], 
                proxy['port']
            )
            
            # SOCKS5 핸드셰이크
            # 1. 인증 방법 협상 (인증 없음: 0x00)
            writer.write(struct.pack('BBB', 5, 1, 0))
            await writer.drain()
            
            response = await reader.read(2)
            ver, method = struct.unpack('BB', response)
            
            if ver != 5 or method != 0:
                raise Exception("SOCKS5 핸드셰이크 실패")
            
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
            response = await reader.read(4)
            ver, rep, rsv, atyp = struct.unpack('BBBB', response)
            
            if atyp == 1:  # IPv4
                await reader.read(4)
            elif atyp == 3:  # 도메인
                addr_len = struct.unpack('B', await reader.read(1))[0]
                await reader.read(addr_len)
            elif atyp == 4:  # IPv6
                await reader.read(16)
            
            await reader.read(2)  # 포트
            
            if rep != 0:
                raise Exception(f"원격 프록시 연결 거부 (코드: {rep})")
            
            return reader, writer
            
        except Exception as e:
            raise Exception(f"원격 프록시 연결 실패: {e}")
    
    async def handle_client(self, client_reader, client_writer):
        """클라이언트 요청 처리"""
        remote_writer = None
        
        try:
            # SOCKS5 핸드셰이크
            data = await client_reader.read(2)
            ver, nmethods = struct.unpack('BB', data)
            
            if ver != 5:
                client_writer.close()
                await client_writer.wait_closed()
                return
            
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
            selected_proxy = self.select_proxy()
            
            print(f"[연결] {addr}:{port} → 프록시: {selected_proxy['host']}:{selected_proxy['port']}")
            
            # 원격 프록시를 통해 연결
            try:
                remote_reader, remote_writer = await self.connect_to_remote_proxy(
                    selected_proxy, 
                    addr, 
                    port
                )
                
                # 클라이언트에게 성공 응답
                client_writer.write(struct.pack('BBBBIH', 5, 0, 0, 1, 0, 0))
                await client_writer.drain()
                
                # 양방향 데이터 전달
                await asyncio.gather(
                    self.pipe(client_reader, remote_writer, f"{addr}:{port} → 원격"),
                    self.pipe(remote_reader, client_writer, f"원격 → {addr}:{port}")
                )
                
            except Exception as e:
                print(f"[오류] {addr}:{port} - {str(e)}")
                # 연결 실패 응답
                client_writer.write(struct.pack('BBBBIH', 5, 1, 0, 1, 0, 0))
                await client_writer.drain()
            
        except Exception as e:
            print(f"[오류] 클라이언트 처리 중: {e}")
        
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