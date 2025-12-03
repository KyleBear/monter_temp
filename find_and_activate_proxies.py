"""
cookies_data 디렉토리의 JSON 파일에서 proxy IP를 추출하고,
현재 활성화된 proxy IP와 비교하여 겹치지 않는 IP 30개를 찾아
출력하는 스크립트
"""

import json
import os
import re
from collections import OrderedDict

def extract_proxies_from_cookies(cookies_dir="cookies_data"):
    """쿠키 파일에서 proxy IP 추출 (cookies_data 바로 아래 디렉토리 제외)"""
    proxies = []
    
    if not os.path.exists(cookies_dir):
        print(f"쿠키 디렉토리를 찾을 수 없습니다: {cookies_dir}")
        return proxies
    
    # cookies_data 바로 아래의 JSON 파일만 읽기 (디렉토리 제외)
    for filename in os.listdir(cookies_dir):
        filepath = os.path.join(cookies_dir, filename)
        
        # 디렉토리는 제외, JSON 파일만 처리
        if os.path.isfile(filepath) and filename.endswith('.json'):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    proxy = data.get('proxy')
                    if proxy:
                        # "IP:PORT" 형식을 파싱
                        if ':' in proxy:
                            host, port = proxy.split(':')
                            proxies.append({
                                'host': host,
                                'port': int(port),
                                'proxy_str': proxy,
                                'file': filename
                            })
            except Exception as e:
                print(f"파일 읽기 실패 ({filename}): {e}")
                continue
    
    # 중복 제거 (같은 IP:PORT는 하나만)
    seen = set()
    unique_proxies = []
    for proxy in proxies:
        proxy_key = f"{proxy['host']}:{proxy['port']}"
        if proxy_key not in seen:
            seen.add(proxy_key)
            unique_proxies.append(proxy)
    
    return unique_proxies

def get_all_proxies_from_chain(proxy_chain_file="proxy_config/proxy_chain.py"):
    """proxy_chain.py에서 모든 프록시 목록 추출 (주석 포함)"""
    all_proxies = []
    
    if not os.path.exists(proxy_chain_file):
        print(f"proxy_chain.py 파일을 찾을 수 없습니다: {proxy_chain_file}")
        return all_proxies
    
    with open(proxy_chain_file, 'r', encoding='utf-8') as f:
        content = f.read()
        
        # 주석 포함 모든 프록시 찾기 (정규식 사용)
        # {"host": "...", "port": ...} 형식 (주석 포함)
        pattern = r'\{\s*"host"\s*:\s*"([^"]+)"\s*,\s*"port"\s*:\s*(\d+)\s*\}'
        
        matches = re.findall(pattern, content)
        for host, port in matches:
            all_proxies.append({
                'host': host,
                'port': int(port),
                'proxy_str': f"{host}:{port}"
            })
    
    return all_proxies

def find_non_overlapping_proxies(cookie_proxies, active_proxies, limit=30):
    """겹치지 않는 프록시 찾기"""
    # 활성화된 프록시를 set으로 변환 (빠른 검색)
    active_set = {f"{p['host']}:{p['port']}" for p in active_proxies}
    
    # 겹치지 않는 프록시 찾기
    non_overlapping = []
    for proxy in cookie_proxies:
        proxy_key = proxy['proxy_str']
        if proxy_key not in active_set:
            non_overlapping.append(proxy)
            if len(non_overlapping) >= limit:
                break
    
    return non_overlapping

def main():
    print("=" * 60)
    print("쿠키 파일에서 프록시 IP 추출 및 출력")
    print("=" * 60)
    
    # 1. 쿠키 파일에서 프록시 추출
    print("\n[1단계] 쿠키 파일에서 프록시 IP 추출 중...")
    cookie_proxies = extract_proxies_from_cookies()
    print(f"[OK] 쿠키 파일에서 {len(cookie_proxies)}개의 고유 프록시 발견")
    
    # 2. proxy_chain.py의 모든 프록시 확인 (주석 포함)
    print("\n[2단계] proxy_chain.py의 모든 프록시 확인 중 (주석 포함)...")
    all_chain_proxies = get_all_proxies_from_chain()
    print(f"[OK] proxy_chain.py에 있는 모든 프록시: {len(all_chain_proxies)}개 (주석 포함)")
    
    # 활성화된 프록시만 따로 추출 (주석 없는 라인)
    with open("proxy_config/proxy_chain.py", 'r', encoding='utf-8') as f:
        lines = f.readlines()
    active_proxies = []
    for line in lines:
        if not line.strip().startswith('#') and '"host"' in line and '"port"' in line:
            match = re.search(r'"host"\s*:\s*"([^"]+)"\s*,\s*"port"\s*:\s*(\d+)', line)
            if match:
                active_proxies.append({
                    'host': match.group(1),
                    'port': int(match.group(2)),
                    'proxy_str': f"{match.group(1)}:{match.group(2)}"
                })
    
    print(f"[OK] 현재 활성화된 프록시: {len(active_proxies)}개")
    for p in active_proxies[:5]:
        print(f"  - {p['proxy_str']}")
    if len(active_proxies) > 5:
        print(f"  ... 외 {len(active_proxies) - 5}개")
    
    # 3. 겹치지 않는 프록시 찾기 (proxy_chain.py 전체에 없는 것)
    print("\n[3단계] proxy_chain.py에 없는 프록시 찾기 중...")
    non_overlapping = find_non_overlapping_proxies(cookie_proxies, all_chain_proxies, limit=30)
    print(f"[OK] 겹치지 않는 프록시 {len(non_overlapping)}개 발견")
    
    if not non_overlapping:
        print("⚠ 활성화할 프록시가 없습니다.")
        return
    
    # 4. proxy_chain.py에서 해당 프록시 찾기 (출력만)
    print("\n[4단계] proxy_chain.py에서 해당 프록시 확인 중...")
    found_in_file = []
    not_found_in_file = []
    
    with open("proxy_config/proxy_chain.py", 'r', encoding='utf-8') as f:
        file_content = f.read()
    
    for proxy in non_overlapping[:30]:
        proxy_key = proxy['proxy_str']
        # 파일에서 해당 IP:PORT 찾기 (주석 처리된 것 포함)
        host = proxy['host']
        port = proxy['port']
        
        # 주석 처리된 라인에서 찾기
        pattern = rf'#\s*\{{"host"\s*:\s*"{re.escape(host)}"\s*,\s*"port"\s*:\s*{port}\s*\}\}'
        if re.search(pattern, file_content):
            found_in_file.append(proxy)
        else:
            # 주석 없이 활성화된 것도 확인
            pattern2 = rf'\{{"host"\s*:\s*"{re.escape(host)}"\s*,\s*"port"\s*:\s*{port}\s*\}\}'
            if re.search(pattern2, file_content):
                found_in_file.append(proxy)
            else:
                not_found_in_file.append(proxy)
    
    print(f"\n[결과] proxy_chain.py에서 찾은 프록시: {len(found_in_file)}개")
    print(f"[결과] proxy_chain.py에 없는 프록시: {len(not_found_in_file)}개")
    
    # 5. 최종 결과 출력
    print("\n" + "=" * 60)
    print("proxy_chain.py에 없는 프록시 목록 (상위 30개):")
    print("=" * 60)
    for i, proxy in enumerate(not_found_in_file[:30], 1):
        print(f"{i:2d}. {proxy['proxy_str']:25s} (파일: {proxy['file']})")
    print("=" * 60)
    
    # proxy_chain.py에 추가할 형식으로 출력
    print("\n" + "=" * 60)
    print("proxy_chain.py에 추가할 형식:")
    print("=" * 60)
    for proxy in not_found_in_file[:30]:
        print(f'{{"host": "{proxy["host"]}", "port": {proxy["port"]}}},')
    print("=" * 60)

if __name__ == '__main__':
    main()

