# test_proxy_connection.py
import asyncio
import struct
import socket
import os
from datetime import datetime

async def test_proxy(host, port):
    """프록시 연결 테스트"""
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

async def test_all_proxies():
    """
    iplist.txt의 모든 프록시를 테스트하고 성공한 프록시 리스트 반환
    
    Returns:
        list: 성공한 프록시 리스트 [{"host": str, "port": int}, ...]
    """
    # 시작 시간 기록
    start_time = datetime.now()
    start_time_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
    
    print("=" * 60)
    print("프록시 연결 테스트 시작")
    print(f"시작 시간: {start_time_str}")
    print("=" * 60)
    
    proxies = []
    iplist_path = "iplist.txt"

    # 현재 디렉토리 또는 상위 디렉토리에서 iplist.txt 찾기
    if not os.path.exists(iplist_path):
        iplist_path = os.path.join("..", "iplist.txt")
    
    if not os.path.exists(iplist_path):
        print(f"✗ iplist.txt 파일을 찾을 수 없습니다: {iplist_path}")
        return []
    
    try:
        with open(iplist_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # 주석이나 빈 줄 건너뛰기
                if not line or line.startswith('#'):
                    continue
                
                # IP:포트 형식 파싱
                if ':' in line:
                    parts = line.split(':')
                    if len(parts) == 2:
                        host = parts[0].strip()
                        try:
                            port = int(parts[1].strip())
                            proxies.append((host, port))
                        except ValueError:
                            print(f"⚠ 포트 번호 파싱 실패: {line}")
        
        print(f"📋 총 {len(proxies)}개의 프록시를 로드했습니다")
        print("=" * 60)
        
        # 각 프록시 테스트
        success_proxies = []
        success_count = 0
        for host, port in proxies:
            result = await test_proxy(host, port)
            if result:
                success_count += 1
                success_proxies.append({"host": host, "port": port})
        
        # 종료 시간 기록
        end_time = datetime.now()
        end_time_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
        elapsed_time = end_time - start_time
        elapsed_seconds = elapsed_time.total_seconds()
        
        print("=" * 60)
        print(f"테스트 완료: {success_count}/{len(proxies)}개 성공")
        print("=" * 60)
        print(f"시작 시간: {start_time_str}")
        print(f"종료 시간: {end_time_str}")
        print(f"총 소요 시간: {elapsed_seconds:.2f}초 ({elapsed_seconds/60:.2f}분)")
        print("=" * 60)
        
        return success_proxies
        
    except Exception as e:
        # 오류 발생 시에도 시간 기록
        end_time = datetime.now()
        end_time_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
        elapsed_time = end_time - start_time
        elapsed_seconds = elapsed_time.total_seconds()
        
        print(f"✗ iplist.txt 읽기 실패: {e}")
        print("=" * 60)
        print(f"시작 시간: {start_time_str}")
        print(f"종료 시간: {end_time_str}")
        print(f"총 소요 시간: {elapsed_seconds:.2f}초 ({elapsed_seconds/60:.2f}분)")
        print("=" * 60)
        return []

async def main():
    """메인 함수 (직접 실행 시)"""
    await test_all_proxies()

if __name__ == '__main__':
    asyncio.run(main())