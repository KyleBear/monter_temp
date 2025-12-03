"""
프록시 IP 연결 테스트 및 DB 저장
proxy_status 테이블과 연동
"""
import asyncio
import struct
import socket
import os
from datetime import datetime
from sqlalchemy import create_engine, Column, BigInteger, String, Integer, Float, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func

# DB 설정 (MySQL 예시)
DATABASE_URL = "mysql+pymysql://user:password@localhost:3306/dbname"
# 또는 PostgreSQL: "postgresql://user:password@localhost:5432/dbname"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ORM 모델
class ProxyStatus(Base):
    __tablename__ = 'proxy_status'
    
    proxy_id = Column(BigInteger, primary_key=True, autoincrement=True)
    proxy_ip = Column(String(45), nullable=False)
    proxy_port = Column(Integer, nullable=False)
    latency_ms = Column(Float, nullable=True)
    success_rate = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)
    last_checked = Column(DateTime, default=func.now(), onupdate=func.now())

async def test_proxy(host, port):
    """프록시 연결 테스트 및 지연 시간 측정"""
    start_time = datetime.now()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=5.0
        )
        elapsed = (datetime.now() - start_time).total_seconds() * 1000  # ms
        writer.close()
        await writer.wait_closed()
        return True, elapsed
    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds() * 1000
        return False, elapsed

async def test_all_proxies_and_save():
    """모든 프록시 테스트 후 DB에 저장/업데이트"""
    start_time = datetime.now()
    print("=" * 60)
    print("프록시 연결 테스트 및 DB 저장 시작")
    print(f"시작 시간: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    proxies = []
    iplist_path = "iplist.txt"
    
    if not os.path.exists(iplist_path):
        iplist_path = os.path.join("..", "iplist.txt")
    
    if not os.path.exists(iplist_path):
        print(f"✗ iplist.txt 파일을 찾을 수 없습니다")
        return
    
    # iplist.txt 읽기
    try:
        with open(iplist_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if ':' in line:
                    parts = line.split(':')
                    if len(parts) == 2:
                        host = parts[0].strip()
                        try:
                            port = int(parts[1].strip())
                            proxies.append((host, port))
                        except ValueError:
                            continue
    except Exception as e:
        print(f"✗ iplist.txt 읽기 실패: {e}")
        return
    
    print(f"📋 총 {len(proxies)}개의 프록시를 로드했습니다")
    print("=" * 60)
    
    # DB 세션 생성
    db = SessionLocal()
    
    try:
        success_count = 0
        for host, port in proxies:
            success, latency = await test_proxy(host, port)
            
            # DB에서 기존 레코드 확인
            proxy = db.query(ProxyStatus).filter(
                ProxyStatus.proxy_ip == host,
                ProxyStatus.proxy_port == port
            ).first()
            
            if proxy:
                # 업데이트
                proxy.latency_ms = latency if success else None
                proxy.is_active = success
                proxy.last_checked = datetime.now()
                # 성공률 계산 (간단한 예시: 최근 10회 중 성공률)
                if success:
                    proxy.success_rate = (proxy.success_rate or 0) * 0.9 + 100 * 0.1
                else:
                    proxy.success_rate = (proxy.success_rate or 0) * 0.9
                print(f"{'✓' if success else '✗'} {host}:{port} - {latency:.2f}ms (업데이트)")
            else:
                # 새로 생성
                proxy = ProxyStatus(
                    proxy_ip=host,
                    proxy_port=port,
                    latency_ms=latency if success else None,
                    is_active=success,
                    success_rate=100.0 if success else 0.0,
                    last_checked=datetime.now()
                )
                db.add(proxy)
                print(f"{'✓' if success else '✗'} {host}:{port} - {latency:.2f}ms (신규)")
            
            if success:
                success_count += 1
        
        # 커밋
        db.commit()
        
        end_time = datetime.now()
        elapsed = (end_time - start_time).total_seconds()
        
        print("=" * 60)
        print(f"테스트 완료: {success_count}/{len(proxies)}개 성공")
        print(f"DB 저장 완료")
        print(f"총 소요 시간: {elapsed:.2f}초")
        print("=" * 60)
        
    except Exception as e:
        db.rollback()
        print(f"✗ DB 저장 실패: {e}")
    finally:
        db.close()

async def get_active_proxies():
    """활성화된 프록시 목록 조회"""
    db = SessionLocal()
    try:
        proxies = db.query(ProxyStatus).filter(
            ProxyStatus.is_active == True
        ).order_by(ProxyStatus.latency_ms).all()
        
        return [{"host": p.proxy_ip, "port": p.proxy_port} for p in proxies]
    finally:
        db.close()

async def main():
    """메인 함수"""
    await test_all_proxies_and_save()

if __name__ == '__main__':
    asyncio.run(main())