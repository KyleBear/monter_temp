"""
휴대폰 Chrome 직접 제어 크롤링 (Selenium 없이)
ADB + Chrome DevTools Protocol을 사용하여 휴대폰 Chrome을 직접 제어합니다.

사용 전 설정:
1. Android 휴대폰에서 개발자 옵션 활성화 및 USB 디버깅 활성화
2. 휴대폰이 USB로 PC에 연결되어 있어야 함
3. Chrome DevTools Protocol을 사용하기 위해 포트 포워딩 필요
"""
import time
import logging
import json
import requests
import websocket
import socket
import subprocess
import platform
from config import Config
from adb_manager import get_adb_manager
import re
from test6 import DataConnectionManager
# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_mobile_external_ip_via_selenium(driver, retry_count=3, retry_delay=2):
    """
    Selenium을 통해 휴대폰의 외부 IP 주소 확인 (curl/wget 불필요)
    
    Args:
        driver: Selenium WebDriver 인스턴스
        retry_count: 재시도 횟수
        retry_delay: 재시도 간 대기 시간
    
    Returns:
        str: 외부 IP 주소, 실패 시 None
    """
    services = [
        'https://api.ipify.org',
        'https://ifconfig.me/ip',
        'https://icanhazip.com',
        'https://api.ip.sb/ip',
        'https://checkip.amazonaws.com'
    ]
    
    for attempt in range(retry_count):
        logger.info(f"외부 IP 확인 시도 {attempt + 1}/{retry_count} (Selenium 사용)...")
        
        for service in services:
            try:
                # JavaScript fetch를 사용하여 IP 확인
                script = f"""
                (async function() {{
                    try {{
                        const response = await fetch('{service}');
                        const ip = await response.text();
                        return ip.trim();
                    }} catch (e) {{
                        return null;
                    }}
                }})();
                """
                
                # JavaScript 실행 (Promise 반환)
                ip = driver.execute_async_script(script)
                
                if ip and isinstance(ip, str):
                    ip = ip.strip()
                    # IPv4 형식 확인
                    if ip and len(ip.split('.')) == 4:
                        # 로컬 IP 제외
                        if not ip.startswith('127.') and not ip.startswith('192.168.') and not ip.startswith('10.') and not ip.startswith('172.'):
                            logger.info(f"✓ 휴대폰 외부 IP 확인 성공 ({service}): {ip}")
                            return ip
                        else:
                            logger.debug(f"로컬 IP 감지됨: {ip}")
                
            except Exception as e:
                logger.debug(f"외부 IP 확인 시도 실패 ({service}): {e}")
                continue
        
        if attempt < retry_count - 1:
            logger.warning(f"휴대폰 외부 IP 확인 실패, {retry_delay}초 후 재시도... ({attempt + 1}/{retry_count})")
            time.sleep(retry_delay)
    
    logger.warning("휴대폰 외부 IP를 확인할 수 없습니다.")
    return None
    
    for attempt in range(retry_count):
        logger.info(f"외부 IP 확인 시도 {attempt + 1}/{retry_count}...")
        
        for service in services:
            try:
                # curl 사용 시도
                if curl_available:
                    logger.debug(f"curl로 {service} 시도 중...")
                    result = adb.run_command('shell', 'curl', '-s', '--max-time', '5', service, timeout=10)
                    
                    logger.debug(f"curl 결과 - returncode: {result.returncode}, stdout: {result.stdout[:100] if result.stdout else None}, stderr: {result.stderr[:100] if hasattr(result, 'stderr') and result.stderr else None}")
                    
                    if result.returncode == 0 and result.stdout:
                        ip = result.stdout.strip()
                        # 불필요한 문자 제거
                        ip = ip.split()[0] if ip.split() else ip
                        logger.debug(f"파싱된 IP: {ip}")
                        
                        # IPv4 형식 확인
                        if ip and len(ip.split('.')) == 4:
                            # 로컬 IP 제외
                            if not ip.startswith('127.') and not ip.startswith('192.168.') and not ip.startswith('10.') and not ip.startswith('172.'):
                                logger.info(f"✓ 휴대폰 외부 IP 확인 성공 ({service}): {ip}")
                                return ip
                            else:
                                logger.debug(f"로컬 IP 감지됨: {ip}")
                
                # wget 사용 시도
                if wget_available and not curl_available:
                    logger.debug(f"wget로 {service} 시도 중...")
                    result = adb.run_command('shell', 'wget', '-qO-', '--timeout=5', service, timeout=10)
                    
                    logger.debug(f"wget 결과 - returncode: {result.returncode}, stdout: {result.stdout[:100] if result.stdout else None}")
                    
                    if result.returncode == 0 and result.stdout:
                        ip = result.stdout.strip()
                        ip = ip.split()[0] if ip.split() else ip
                        logger.debug(f"파싱된 IP: {ip}")
                        
                        if ip and len(ip.split('.')) == 4:
                            if not ip.startswith('127.') and not ip.startswith('192.168.') and not ip.startswith('10.') and not ip.startswith('172.'):
                                logger.info(f"✓ 휴대폰 외부 IP 확인 성공 ({service}, wget): {ip}")
                                return ip
                            else:
                                logger.debug(f"로컬 IP 감지됨: {ip}")
                            
            except Exception as e:
                logger.debug(f"외부 IP 확인 시도 실패 ({service}): {e}", exc_info=True)
                continue
        
        # 재시도 전 대기
        if attempt < retry_count - 1:
            logger.warning(f"휴대폰 외부 IP 확인 실패, {retry_delay}초 후 재시도... ({attempt + 1}/{retry_count})")
            time.sleep(retry_delay)
    
    logger.warning("휴대폰 외부 IP를 확인할 수 없습니다.")
    logger.warning("가능한 원인:")
    logger.warning("1. 휴대폰에 curl/wget이 설치되어 있지 않음")
    logger.warning("2. 휴대폰의 인터넷 연결이 없음")
    logger.warning("3. 방화벽이나 네트워크 설정 문제")
    logger.warning("4. IP 확인 서비스 접근 불가")
    return None


def get_mobile_ip(adb, retry_count=3, retry_delay=2):
    """휴대폰의 외부 IP 주소 확인 (공인 IP) - get_mobile_external_ip의 별칭"""
    return get_mobile_external_ip(adb, retry_count, retry_delay)

class ChromeDevTools:
    """Chrome DevTools Protocol 클라이언트"""
    
    def __init__(self, host='localhost', port=9222):
        self.host = host
        self.port = port
        self.base_url = f'http://{host}:{port}'
        self.ws_url = None
        self.ws = None
        self.target_id = None
        self.command_id = 0
        
    def connect(self):
        """Chrome DevTools에 연결"""
        try:
            # 사용 가능한 타겟 목록 가져오기
            response = requests.get(f'{self.base_url}/json', timeout=5)
            targets = response.json()
            
            if not targets:
                logger.error("연결된 Chrome 타겟이 없습니다.")
                return False
            
            # 첫 번째 웹 페이지 타겟 찾기
            for target in targets:
                if target.get('type') == 'page':
                    self.target_id = target['id']
                    self.ws_url = target['webSocketDebuggerUrl']
                    logger.info(f"타겟 찾음: {target.get('title', 'Unknown')}")
                    break
            
            if not self.ws_url:
                logger.error("웹 페이지 타겟을 찾을 수 없습니다.")
                return False
            
            # WebSocket 연결 (타임아웃 30초로 증가)
            self.ws = websocket.create_connection(self.ws_url, timeout=30)
            # 소켓 레벨 타임아웃 설정 (recv 타임아웃)
            self.ws.sock.settimeout(30)
            logger.info("✓ Chrome DevTools 연결 완료")
            return True
            
        except Exception as e:
            logger.error(f"Chrome DevTools 연결 실패: {e}")
            return False
    
    def send_command(self, method, params=None, timeout=30):
        """명령 전송"""
        if not self.ws:
            logger.error("WebSocket이 연결되지 않았습니다.")
            return None
        
        self.command_id += 1
        command = {
            'id': self.command_id,
            'method': method,
            'params': params or {}
        }
        
        try:
            # 소켓 타임아웃 설정 (recv 전에)
            if hasattr(self.ws, 'sock') and self.ws.sock:
                self.ws.sock.settimeout(timeout)
            
            logger.debug(f"send_command: 명령 전송 시작 - 메서드: {method}, ID: {self.command_id}")
            self.ws.send(json.dumps(command))
            logger.debug(f"send_command: 명령 전송 완료, 응답 대기 중...")
            response = self.ws.recv()
            logger.debug(f"send_command: 응답 수신 완료, 길이: {len(response) if response else 0}")
            result = json.loads(response)
            
            if 'error' in result:
                logger.error(f"명령 실행 오류: {result['error']}")
                return None
            
            logger.debug(f"send_command: 명령 실행 성공 - 메서드: {method}, ID: {self.command_id}")
            return result
        except websocket.WebSocketTimeoutException as e:
            logger.error(f"명령 전송 중 타임아웃 오류 (메서드: {method}): {e}")
            return None
        except (socket.timeout, TimeoutError) as e:
            logger.error(f"명령 전송 중 소켓 타임아웃 오류 (메서드: {method}): {e}")
            return None
        except Exception as e:
            logger.error(f"명령 전송 중 오류 (메서드: {method}): {e}", exc_info=True)
            return None
    
    def execute_script(self, script):
        """JavaScript 실행"""
        result = self.send_command('Runtime.evaluate', {
            'expression': script,
            'returnByValue': True,
            'awaitPromise': False,  # Promise 대기 안 함 (타임아웃 방지)
            'userGesture': False
        })

        if result is None:
            logger.warning("execute_script: send_command가 None을 반환했습니다 (타임아웃 또는 연결 오류 가능)")
            return None

        if 'result' not in result:
            logger.warning(f"execute_script: result에 'result' 키가 없습니다. 반환값: {result}")
            if 'error' in result:
                logger.error(f"execute_script: CDP 오류 - {result['error']}")
            return None

        result_value = result['result']
        result_type = result_value.get('type')
        result_object_id = result_value.get('objectId')
        result_value_data = result_value.get('value')
        logger.info(f"execute_script: result_value 타입={result_type}, objectId={result_object_id}, value={result_value_data}")
        
        # value가 있는 경우 (returnByValue: True일 때 객체도 value 안에 직렬화됨)
        if 'value' in result_value:
            value = result_value['value']
            # value가 객체(dict)인 경우 그대로 반환
            if isinstance(value, dict):
                logger.info(f"execute_script: value 안의 객체 반환 - {value}")
                return value
            else:
                logger.debug(f"execute_script: value 반환 - {value}")
                return value
        
        # type이 있는 경우
        if 'type' in result_value:
            result_type = result_value['type']
            
            # boolean, number, string 등 기본 타입
            if result_type in ['boolean', 'number', 'string', 'bigint']:
                value = result_value.get('value')
                logger.debug(f"execute_script: {result_type} 타입 반환 - {value}")
                return value
            
            # undefined 타입
            elif result_type == 'undefined':
                logger.debug("execute_script: undefined 반환")
                return None
            
            # object 타입 (returnByValue: False인 경우)
            elif result_type == 'object':
                # objectId가 있으면 객체 속성을 가져와서 딕셔너리로 변환
                if 'objectId' in result_value:
                    try:
                        logger.info(f"execute_script: objectId로 속성 가져오기 시도 - {result_value['objectId']}")
                        props_result = self.send_command('Runtime.getProperties', {
                            'objectId': result_value['objectId'],
                            'ownProperties': True
                        })
                        if props_result and 'result' in props_result:
                            props = {}
                            for prop in props_result['result']:
                                if 'name' in prop and 'value' in prop:
                                    prop_value = prop['value']
                                    # 중첩된 객체도 처리
                                    if 'value' in prop_value:
                                        props[prop['name']] = prop_value['value']
                                    elif prop_value.get('type') == 'object' and 'objectId' in prop_value:
                                        # 중첩 객체도 재귀적으로 처리 (debug 객체 등)
                                        try:
                                            nested_props_result = self.send_command('Runtime.getProperties', {
                                                'objectId': prop_value['objectId'],
                                                'ownProperties': True
                                            })
                                            if nested_props_result and 'result' in nested_props_result:
                                                nested_props = {}
                                                for nested_prop in nested_props_result['result']:
                                                    if 'name' in nested_prop and 'value' in nested_prop:
                                                        nested_prop_value = nested_prop['value']
                                                        if 'value' in nested_prop_value:
                                                            nested_props[nested_prop['name']] = nested_prop_value['value']
                                                        else:
                                                            nested_props[nested_prop['name']] = nested_prop_value.get('value', nested_prop_value)
                                                props[prop['name']] = nested_props
                                            else:
                                                props[prop['name']] = prop_value.get('description', 'object')
                                        except Exception as e:
                                            logger.debug(f"중첩 객체 속성 가져오기 실패: {e}")
                                            props[prop['name']] = prop_value.get('description', 'object')
                                    else:
                                        props[prop['name']] = prop_value.get('value', prop_value)
                            logger.info(f"execute_script: 객체 반환 - {props}")
                            return props
                        else:
                            logger.warning(f"execute_script: Runtime.getProperties 실패 - {props_result}")
                    except Exception as e:
                        logger.warning(f"객체 속성 가져오기 실패: {e}")
                        # 실패 시 description이나 기본 정보 반환
                        return result_value.get('description', result_value)
                # objectId가 없으면 description이나 기본 정보 반환
                return result_value.get('description', result_value)
            
            # function, symbol 등 기타 타입
            else:
                value = result_value.get('value')
                logger.debug(f"execute_script: {result_type} 타입 반환 - {value}")
                return value
        
        logger.warning(f"execute_script: 예상치 못한 result_value 형식: {result_value}")
        return None
    
    def navigate(self, url):
        """페이지 이동"""
        result = self.send_command('Page.navigate', {'url': url})
        return result is not None and 'error' not in result
    
    def wait_for_load(self, timeout=10):
        """페이지 로드 대기"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            result = self.send_command('Page.getNavigationHistory')
            if result and 'result' in result:
                return True
            time.sleep(0.5)
        return False

    def get_current_url(self):
        """현재 URL 가져오기"""
        try:
            # 방법 1: Page.getNavigationHistory
            logger.debug("get_current_url: Page.getNavigationHistory 시도")
            result = self.send_command('Page.getNavigationHistory')
            logger.debug(f"get_current_url: result = {result}")
            
            if result and 'result' in result:
                entries = result['result'].get('entries', [])
                current_index = result['result'].get('currentIndex', -1)
                logger.debug(f"get_current_url: entries 개수 = {len(entries)}, current_index = {current_index}")
                
                if entries and 0 <= current_index < len(entries):
                    url = entries[current_index].get('url')
                    logger.info(f"현재 URL (Navigation History): {url}")
                    return url
            
            # 방법 2: JavaScript
            logger.debug("get_current_url: JavaScript 시도")
            result = self.execute_script("window.location.href")
            logger.debug(f"get_current_url: JavaScript result = {result}")
            
            if result:
                logger.info(f"현재 URL (JavaScript): {result}")
                return result
            
            logger.warning("현재 URL을 가져올 수 없습니다.")
            return None
            
        except Exception as e:
            logger.error(f"get_current_url 오류: {e}", exc_info=True)
            return None

    def close(self):
        """연결 종료"""
        if self.ws:
            try:
                self.ws.close()
            except:
                pass
            self.ws = None

    def navigate_back(self):
        """뒤로가기 (CDP 네이티브 명령어)"""
        try:
            # Page.getNavigationHistory로 히스토리 가져오기
            result = self.send_command('Page.getNavigationHistory')
            if not result or 'result' not in result:
                logger.error("네비게이션 히스토리를 가져올 수 없습니다.")
                return False
            
            entries = result['result'].get('entries', [])
            current_index = result['result'].get('currentIndex', -1)
            
            # 뒤로갈 페이지가 있는지 확인
            if current_index <= 0:
                logger.warning("뒤로갈 페이지가 없습니다.")
                return False
            
            # 이전 페이지의 entryId 가져오기
            previous_entry = entries[current_index - 1]
            previous_entry_id = previous_entry.get('id')
            
            # Page.navigateToHistoryEntry로 이동
            result = self.send_command('Page.navigateToHistoryEntry', {
                'entryId': previous_entry_id
            })
            
            if result:
                logger.debug(f"뒤로가기 성공: {previous_entry.get('url')}")
                return True
            else:
                logger.error("뒤로가기 실패")
                return False
                
        except Exception as e:
            logger.error(f"뒤로가기 중 오류: {e}")
            return False
    
    def navigate_back_multiple(self, steps=2):
        """여러 번 뒤로가기"""
        try:
            # Page.getNavigationHistory로 히스토리 가져오기
            result = self.send_command('Page.getNavigationHistory')
            if not result or 'result' not in result:
                logger.error("네비게이션 히스토리를 가져올 수 없습니다.")
                return False
            
            entries = result['result'].get('entries', [])
            current_index = result['result'].get('currentIndex', -1)
            
            # 뒤로갈 수 있는지 확인
            target_index = current_index - steps
            if target_index < 0:
                logger.warning(f"{steps}번 뒤로갈 수 없습니다. (현재 인덱스: {current_index})")
                target_index = 0
            
            # 목표 페이지의 entryId 가져오기
            target_entry = entries[target_index]
            target_entry_id = target_entry.get('id')
            target_url = target_entry.get('url')
            
            logger.info(f"{steps}번 뒤로가기: {target_url}")
            
            # Page.navigateToHistoryEntry로 이동
            result = self.send_command('Page.navigateToHistoryEntry', {
                'entryId': target_entry_id
            })
            
            if result is not None:
                logger.info(f"✓ {steps}번 뒤로가기 성공")
                return True
            else:
                logger.error("뒤로가기 실패")
                return False
                
        except Exception as e:
            logger.error(f"뒤로가기 중 오류: {e}", exc_info=True)
            return False

def get_port_process_info(port):
    """
    특정 포트를 사용하는 프로세스 정보 조회
    
    Args:
        port: 포트 번호
    
    Returns:
        dict: 프로세스 정보 (pid, name, command) 또는 None
    """
    try:
        system = platform.system()
        
        if system == 'Windows':
            # Windows: netstat으로 포트 사용 프로세스 PID 확인
            try:
                netstat_result = subprocess.run(
                    ['netstat', '-ano'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if netstat_result.returncode == 0:
                    lines = netstat_result.stdout.split('\n')
                    pid = None
                    
                    for line in lines:
                        if f':{port}' in line and 'LISTENING' in line:
                            parts = line.split()
                            if len(parts) >= 5:
                                pid = parts[-1]
                                break
                    
                    if pid:
                        # tasklist로 프로세스 이름 확인
                        try:
                            tasklist_result = subprocess.run(
                                ['tasklist', '/FI', f'PID eq {pid}', '/FO', 'CSV', '/NH'],
                                capture_output=True,
                                text=True,
                                timeout=5
                            )
                            
                            if tasklist_result.returncode == 0 and tasklist_result.stdout.strip():
                                # CSV 형식 파싱: "이미지 이름","PID","세션 이름","세션#","메모리 사용"
                                parts = tasklist_result.stdout.strip().split('","')
                                if len(parts) >= 1:
                                    process_name = parts[0].strip('"')
                                    
                                    # wmic으로 전체 명령줄 확인
                                    try:
                                        wmic_result = subprocess.run(
                                            ['wmic', 'process', 'where', f'ProcessId={pid}', 'get', 'CommandLine', '/format:list'],
                                            capture_output=True,
                                            text=True,
                                            timeout=5
                                        )
                                        command_line = None
                                        if wmic_result.returncode == 0:
                                            for line in wmic_result.stdout.split('\n'):
                                                if line.startswith('CommandLine='):
                                                    command_line = line.replace('CommandLine=', '').strip()
                                                    break
                                        
                                        return {
                                            'pid': pid,
                                            'name': process_name,
                                            'command': command_line or 'N/A'
                                        }
                                    except Exception as e:
                                        logger.debug(f"wmic 명령 실행 실패: {e}")
                                        return {
                                            'pid': pid,
                                            'name': process_name,
                                            'command': 'N/A'
                                        }
                        except Exception as e:
                            logger.debug(f"tasklist 명령 실행 실패: {e}")
                            return {'pid': pid, 'name': 'N/A', 'command': 'N/A'}
            except Exception as e:
                logger.debug(f"netstat 명령 실행 실패: {e}")
        
        elif system in ['Linux', 'Darwin']:  # Linux or macOS
            try:
                # lsof로 포트 사용 프로세스 확인
                lsof_result = subprocess.run(
                    ['lsof', '-i', f':{port}'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if lsof_result.returncode == 0 and lsof_result.stdout.strip():
                    lines = lsof_result.stdout.strip().split('\n')
                    if len(lines) > 1:  # 헤더 제외
                        parts = lines[1].split()
                        if len(parts) >= 2:
                            pid = parts[1]
                            name = parts[0]
                            command = ' '.join(parts[8:]) if len(parts) > 8 else 'N/A'
                            return {
                                'pid': pid,
                                'name': name,
                                'command': command
                            }
            except Exception as e:
                logger.debug(f"lsof 명령 실행 실패: {e}")
        
        return None
    except Exception as e:
        logger.debug(f"포트 프로세스 정보 조회 실패: {e}")
        return None


def check_port_in_use(port):
    """
    포트가 사용 중인지 확인 (소켓 연결 시도)
    
    Args:
        port: 포트 번호
    
    Returns:
        bool: 포트가 사용 중이면 True
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result == 0
    except Exception:
        return False


def setup_port_forwarding(adb, port=9222):
    """ADB 포트 포워딩 설정 (상세 로깅 포함)"""
    try:
        logger.info(f"[포트 포워딩] 포트 {port} 설정 시작")
        
        # 포트 사용 여부 확인
        port_in_use = check_port_in_use(port)
        if port_in_use:
            logger.warning(f"[포트 포워딩] 포트 {port}가 이미 사용 중입니다. 프로세스 정보 확인 중...")
            process_info = get_port_process_info(port)
            if process_info:
                logger.warning(f"[포트 포워딩] 포트 {port}를 사용하는 프로세스:")
                logger.warning(f"  - PID: {process_info['pid']}")
                logger.warning(f"  - 프로세스 이름: {process_info['name']}")
                logger.warning(f"  - 명령줄: {process_info['command']}")
            else:
                logger.warning(f"[포트 포워딩] 포트 {port}를 사용하는 프로세스 정보를 가져올 수 없습니다.")
        
        # 기존 포워딩 제거 (여러 번 시도)
        logger.debug(f"[포트 포워딩] 기존 포트 포워딩 제거 시도 (포트: {port})")
        for attempt in range(3):
            try:
                result = adb.run_command('forward', '--remove', f'tcp:{port}', timeout=3)
                if result.returncode == 0:
                    logger.debug(f"[포트 포워딩] 기존 포트 포워딩 제거 완료 (포트: {port}, 시도: {attempt + 1})")
                    break
                else:
                    error_msg = result.stderr if hasattr(result, 'stderr') and result.stderr else str(result)
                    logger.debug(f"[포트 포워딩] 기존 포트 포워딩 제거 시도 {attempt + 1}/3: {error_msg}")
            except Exception as e:
                logger.debug(f"[포트 포워딩] 기존 포트 포워딩 제거 시도 {attempt + 1}/3 실패: {e}")
                if attempt < 2:
                    time.sleep(1)
        
        # 잠시 대기 (포트 해제 대기)
        time.sleep(0.5)
        
        # 포트 포워딩 설정
        logger.info(f"[포트 포워딩] 포트 포워딩 설정 시도 (tcp:{port} -> localabstract:chrome_devtools_remote)")
        result = adb.run_command('forward', f'tcp:{port}', 'localabstract:chrome_devtools_remote', timeout=5)
        
        if result.returncode == 0:
            logger.info(f"✓ [포트 포워딩] 포트 포워딩 설정 완료 (localhost:{port} -> 기기 Chrome)")
            
            # 설정 후 포트 상태 확인
            time.sleep(0.5)
            final_port_in_use = check_port_in_use(port)
            if final_port_in_use:
                logger.debug(f"[포트 포워딩] 포트 {port}가 정상적으로 리스닝 중입니다.")
            else:
                logger.warning(f"[포트 포워딩] 포트 {port}가 리스닝 상태가 아닙니다.")
            
            return True
        else:
            error_msg = result.stderr if hasattr(result, 'stderr') and result.stderr else str(result)
            logger.error(f"✗ [포트 포워딩] 포트 포워딩 설정 실패 (포트: {port})")
            logger.error(f"  - 에러 메시지: {error_msg}")
            logger.error(f"  - 반환 코드: {result.returncode}")
            
            # 실패 후 포트 상태 재확인
            process_info = get_port_process_info(port)
            if process_info:
                logger.error(f"  - 포트 {port}를 사용하는 프로세스:")
                logger.error(f"    * PID: {process_info['pid']}")
                logger.error(f"    * 프로세스 이름: {process_info['name']}")
                logger.error(f"    * 명령줄: {process_info['command']}")
            
            # ADB 연결 상태 확인
            try:
                if adb.check_connection():
                    logger.debug(f"  - ADB 연결 상태: 정상")
                else:
                    logger.error(f"  - ADB 연결 상태: 끊어짐")
            except Exception as e:
                logger.error(f"  - ADB 연결 상태 확인 실패: {e}")
            
            return False
    except Exception as e:
        logger.error(f"✗ [포트 포워딩] 포트 포워딩 설정 중 예외 발생 (포트: {port}): {e}", exc_info=True)
        
        # 예외 발생 시 포트 상태 확인
        try:
            process_info = get_port_process_info(port)
            if process_info:
                logger.error(f"  - 포트 {port}를 사용하는 프로세스:")
                logger.error(f"    * PID: {process_info['pid']}")
                logger.error(f"    * 프로세스 이름: {process_info['name']}")
                logger.error(f"    * 명령줄: {process_info['command']}")
        except:
            pass
        
        return False


def restart_mobile_chrome(adb, url=None, enable_data_toggle=True):
    """
    휴대폰 Chrome 재시작
    크롤링 시작 전 IP 변경을 위해 데이터 연결을 켰다 끕니다.
    
    Args:
        adb: ADB Manager 인스턴스
        url: 시작할 URL (선택사항)
        enable_data_toggle: Chrome 시작 시 데이터 연결 켰다 끄기 여부 (IP 변경용)
    """
    try:
        # IP 변경을 위해 데이터 연결 켰다 끄기
        if enable_data_toggle:
            logger.info("크롤링 시작 전 IP 변경을 위해 데이터 연결 토글")
            data_manager = DataConnectionManager(adb=adb)
            data_manager.toggle_data_connection(disable_duration=3)
            time.sleep(5)  # 네트워크 재연결 대기
        
        # Chrome 종료
        logger.info("모든 Chrome 앱 종료 중...")
        result = adb.run_command('shell', 'am', 'force-stop', 'com.android.chrome')
        
        if result.returncode == 0:
            logger.info("✓ Chrome 앱 종료 완료")
        else:
            logger.warning(f"Chrome 종료 실패: {result.stderr}")

        time.sleep(2)
        
        # Chrome 시작
        if url:
            logger.info(f"Chrome 앱을 {url}로 시작 중...")
            result = adb.run_command('shell', 'am', 'start', '-a', 'android.intent.action.VIEW', 
                                     '-d', url, 'com.android.chrome')
        else:
            logger.info("Chrome 앱 시작 중...")
            result = adb.run_command('shell', 'am', 'start', '-n', 
                                     'com.android.chrome/com.google.android.apps.chrome.Main')
        
        if result.returncode == 0:
            logger.info("✓ Chrome 앱 시작 완료")
            logger.info("=" * 50)
            return True
        else:
            logger.error(f"Chrome 시작 실패: {result.stderr}")
            logger.info("=" * 50)
            return False
            
    except Exception as e:
        logger.error(f"Chrome 재시작 중 오류: {e}")
        logger.info("=" * 50)
        return False

def create_click_result_script(config_nvmid):
    """
    NV MID로 검색 결과를 찾아 클릭하는 JavaScript 스크립트 생성
    
    Args:
        config_nvmid: 찾을 NV MID 값
    
    Returns:
        str: 실행할 JavaScript 코드
    """
    click_result_script = f"""
    (function() {{
        var targetNvmid = '{config_nvmid}';
        var targetAriaId = 'view_type_guide_' + targetNvmid;
        var targetResult = null;
        var foundNvmid = null;
        var allFoundNvmids = [];  // 디버깅용
        
        // 요소가 나타날 때까지 대기 (최대 5초)
        var maxWait = 5000;
        var startTime = Date.now();
        var allLinks = [];
        
        // HTML 구조를 차례대로 타고 들어가면서 찾기
        while (targetResult === null && (Date.now() - startTime) < maxWait) {{
            // 1단계: .flicking-viewport 찾기
            var flickingViewport = document.querySelector('.flicking-viewport');
            console.log('1단계: flicking-viewport 존재: ' + !!flickingViewport);
            
            if (flickingViewport) {{
                // 2단계: flicking-viewport 안에서 li.ds9RptR1 찾기
                var listItems = flickingViewport.querySelectorAll('li.ds9RptR1');
                console.log('2단계: li.ds9RptR1 개수: ' + listItems.length);
                
                // 3단계: 각 li를 순회하면서 a 태그 찾기
                for (var i = 0; i < listItems.length; i++) {{
                    var listItem = listItems[i];
                    var link = listItem.querySelector('a[aria-labelledby^="view_type_guide_"]');
                    
                    if (link) {{
                        // 4단계: aria-labelledby 속성에서 view_type_guide_ 뒤의 번호 추출
                        var ariaId = link.getAttribute('aria-labelledby');
                        console.log('3단계: 링크 ' + i + '의 aria-labelledby: ' + ariaId);
                        
                        if (ariaId && ariaId.startsWith('view_type_guide_')) {{
                            var nvmid = ariaId.replace('view_type_guide_', '');
                            allFoundNvmids.push(nvmid);  // 디버깅용
                            console.log('4단계: 추출한 NV MID: ' + nvmid + ', 찾을 NV MID: ' + targetNvmid);
                            
                            // 5단계: 번호가 일치하는지 확인
                            if (nvmid === targetNvmid) {{
                                targetResult = link;
                                foundNvmid = nvmid;
                                console.log('✓ NV MID 일치하는 요소 찾음! 인덱스: ' + i + ', NV MID: ' + nvmid);
                                break;
                            }}
                        }}
                    }}
                }}
            }}
            
            // flicking-viewport가 없거나 찾지 못한 경우, 다른 구조 시도
            if (!targetResult) {{
                // 대안: ul > li.ds9RptR1 구조 찾기
                var ulElements = document.querySelectorAll('ul');
                console.log('대안: ul 요소 개수: ' + ulElements.length);
                
                for (var u = 0; u < ulElements.length; u++) {{
                    var ul = ulElements[u];
                    var listItems = ul.querySelectorAll('li.ds9RptR1');
                    
                    for (var i = 0; i < listItems.length; i++) {{
                        var listItem = listItems[i];
                        var link = listItem.querySelector('a[aria-labelledby^="view_type_guide_"]');
                        
                        if (link) {{
                            var ariaId = link.getAttribute('aria-labelledby');
                            if (ariaId && ariaId.startsWith('view_type_guide_')) {{
                                var nvmid = ariaId.replace('view_type_guide_', '');
                                allFoundNvmids.push(nvmid);
                                
                                if (nvmid === targetNvmid) {{
                                    targetResult = link;
                                    foundNvmid = nvmid;
                                    console.log('✓ NV MID 일치하는 요소 찾음! (ul 구조) 인덱스: ' + i + ', NV MID: ' + nvmid);
                                    break;
                                }}
                            }}
                        }}
                    }}
                    
                    if (targetResult) break;
                }}
            }}
            
            // 여전히 찾지 못한 경우 대기
            if (!targetResult) {{
                var wait = 100;
                var waitUntil = Date.now() + wait;
                while (Date.now() < waitUntil) {{
                    // busy wait
                }}
            }}
        }}
        
        // 디버깅 정보 수집
        if (allLinks.length === 0) {{
            var flickingViewport = document.querySelector('.flicking-viewport');
            if (flickingViewport) {{
                var listItems = flickingViewport.querySelectorAll('li.ds9RptR1');
                for (var i = 0; i < listItems.length; i++) {{
                    var link = listItems[i].querySelector('a[aria-labelledby^="view_type_guide_"]');
                    if (link) {{
                        allLinks.push(link);
                    }}
                }}
            }}
        }}
        
        console.log('총 링크 개수: ' + allLinks.length);
        console.log('찾을 NV MID: ' + targetNvmid);
        console.log('찾은 요소: ' + (targetResult ? '있음' : '없음'));
        
        // 디버깅 정보
        var debugInfo = {{
            totalLinks: allLinks.length,
            targetNvmid: targetNvmid,
            foundNvmids: allFoundNvmids.slice(0, 20),
            found: targetResult !== null,
            matchedNvmid: foundNvmid,
            hasFlickingViewport: !!document.querySelector('.flicking-viewport'),
            hasListItems: document.querySelectorAll('li.ds9RptR1').length
        }};
        console.log('디버깅 정보:', JSON.stringify(debugInfo));
        
        if (targetResult) {{
            // 요소가 보이지 않으면 스크롤 (클릭하기 전에만)
            var rect = targetResult.getBoundingClientRect();
            var isVisible = rect.width > 0 && rect.height > 0 && 
                           rect.top >= 0 && rect.left >= 0 &&
                           rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
                           rect.right <= (window.innerWidth || document.documentElement.clientWidth);
            
            if (!isVisible) {{
                console.log('Element not visible, scrolling to view...');
                targetResult.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                var scrollWait = 500;
                var scrollWaitUntil = Date.now() + scrollWait;
                while (Date.now() < scrollWaitUntil) {{
                    // busy wait
                }}
            }}
            
            // 요소가 클릭 가능한지 확인
            var computedStyle = window.getComputedStyle(targetResult);
            var isClickable = computedStyle.display !== 'none' && 
                             computedStyle.visibility !== 'hidden' &&
                             computedStyle.pointerEvents !== 'none';
            
            if (!isClickable) {{
                console.log('Element is not clickable');
                return {{ success: false, nvmid: foundNvmid, reason: 'not_clickable', debug: debugInfo }};
            }}
            
            console.log('Clicking product with NV MID: ' + foundNvmid);
            
            // 여러 방법으로 클릭 시도
            try {{
                targetResult.click();
            }} catch (e) {{
                console.log('Direct click failed, trying mouse event');
                try {{
                    var clickEvent = new MouseEvent('click', {{
                        view: window,
                        bubbles: true,
                        cancelable: true
                    }});
                    targetResult.dispatchEvent(clickEvent);
                }} catch (e2) {{
                    console.log('MouseEvent click failed, trying href navigation');
                    if (targetResult.href) {{
                        window.location.href = targetResult.href;
                    }} else {{
                        return {{ success: false, nvmid: foundNvmid, reason: 'click_failed', debug: debugInfo }};
                    }}
                }}
            }}
            
            return {{ success: true, nvmid: foundNvmid, debug: debugInfo }};
        }}
        
        return {{ success: false, nvmid: null, reason: 'nvmid_not_found', debug: debugInfo }};
    }})();
    """
    
    return click_result_script

def run_crawling_task_cdtp(chrome_dt, iteration):
    """
    Chrome DevTools Protocol을 사용한 크롤링 작업 (Selenium 없음)
    
    Args:
        chrome_dt: ChromeDevTools 인스턴스
        iteration: 반복 번호
    
    Returns:
        bool: 성공 여부
    """
    config = Config()
    
    try:
        logger.info("=" * 50)
        logger.info(f"Chrome DevTools 기반 크롤링 작업 시작 - 반복: {iteration:02d}")
        logger.info("=" * 50)
        
        # 1. 네이버 접속
        naver_url = config.NAVER_MOBILE_URL
        current_url = chrome_dt.get_current_url()
        logger.info(f"현재 URL: {current_url}")
        
        if not current_url or naver_url not in current_url:
            logger.info(f"네이버 접속: {naver_url}")
            if not chrome_dt.navigate(naver_url):
                logger.error("네이버 접속 실패")
                return False
            chrome_dt.wait_for_load()
            time.sleep(3)
        else:
            logger.info(f"이미 네이버 페이지에 있습니다: {current_url}")
        
        # 2. 메인 키워드 검색
        main_keyword = config.MAIN_KEYWORD_LIST
        logger.info(f"메인 키워드 검색: {main_keyword}")

        search_script = """
        (function() {
            // 가짜 검색창 클릭 (여러 선택자 시도)
            var fakeSearch = document.querySelector('#MM_SEARCH_FAKE') ||
                            document.querySelector('.MM_search_fake') ||
                            document.querySelector('[id*="SEARCH_FAKE"]');

            if (fakeSearch) {
                fakeSearch.scrollIntoView({ behavior: 'smooth', block: 'center' });
                setTimeout(() => {
                    fakeSearch.click();
                }, 300);
                return true;
            }
            return false;
        })();
        """
        chrome_dt.execute_script(search_script)
        time.sleep(1)
        
        # 검색창에 메인 키워드 입력 # 검색 스크립트 및 nvmid 최적화 작업필요
        search_input_script = f"""
        (function() {{
            var searchInput = document.querySelector('#query') || 
                             document.querySelector('input.sch_input') ||
                             document.querySelector('input[type="search"]');
            if (searchInput) {{
                searchInput.focus();
                searchInput.click();
                searchInput.value = '';
                
                searchInput.value = '{main_keyword}';
                searchInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                return true;
            }}
            return false;
        }})();
        """
        result = chrome_dt.execute_script(search_input_script)
        if result:
            logger.info("메인 키워드 검색어 입력 완료")
        else:
            logger.warning(" 메인 키워드 검색창을 찾지 못했습니다.")
            time.sleep(2)
        
        # 검색 버튼 클릭 (별도 스크립트로 분리)
        time.sleep(1)  # 입력 후 잠시 대기

        
        # 3. 검색어 지우고 새 검색어 입력
        base_keyword = config.BASE_SEARCH_KEYWORD_LIST
        search_keyword = f"{base_keyword}"
        logger.info(f"새 기본 검색어 입력: {search_keyword}") #여기서부터 안됨.

        clear_and_search_script = f"""
        (function() {{
            var clearBtn = document.querySelector('button[aria-label*="삭제"]') ||
                          document.querySelector('.btn_delete');
            if (clearBtn) {{
                clearBtn.click();
            }}
        }})();
        """
        chrome_dt.execute_script(clear_and_search_script)

        # 가짜 검색창 클릭 (313번째 줄과 동일한 로직)
        fake_search_script = """
        (function() {
            // 가짜 검색창 클릭 (여러 선택자 시도)
            var fakeSearch = document.querySelector('#MM_SEARCH_FAKE') ||
                            document.querySelector('.MM_search_fake') ||
                            document.querySelector('[id*="SEARCH_FAKE"]');
            
            if (fakeSearch) {
                fakeSearch.scrollIntoView({ behavior: 'smooth', block: 'center' });
                setTimeout(() => {
                    fakeSearch.click();
                }, 300);
                return true;
            }
            return false;
        })();
        """
        chrome_dt.execute_script(fake_search_script)
        time.sleep(1)
        # 새 검색어 입력
        clear_and_search_script = f"""
        (function() {{
            var searchInput = document.querySelector('#query') || 
                             document.querySelector('input.sch_input') ||
                             document.querySelector('input[type="search"]');
            if (searchInput) {{
                searchInput.value = '';
                searchInput.value = '{base_keyword}';
                searchInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                searchInput.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', code: 'Enter' }}));
                return true;
            }}
            return false;
        }})();
        """
        chrome_dt.execute_script(clear_and_search_script)
        time.sleep(1)
        # 검색 버튼 클릭 (BASE 검색어용)
        search_button_script = """
        (function() {
            var searchButton = document.querySelector('button.sch_btn_search') ||
                              document.querySelector('button.MM_SEARCH_SUBMIT') ||
                              document.querySelector('#sch_w > div > form > button') ||
                              document.querySelector('button[type="submit"]');
            
            if (searchButton) {
                searchButton.click();
                return true;
            }
            
            // 버튼을 찾지 못하면 form submit 시도
            var searchInput = document.querySelector('#query') || 
                             document.querySelector('input.sch_input');
            if (searchInput) {
                var form = searchInput.closest('form');
                if (form) {
                    form.submit();
                    return true;
                }
            }
            
            return false;
        })();
        """

        button_result = chrome_dt.execute_script(search_button_script)
        if button_result:
            logger.info(" 기본 검색어 검색 버튼 클릭 완료")
        else:
            logger.warning("기본 검색어 검색 버튼을 찾지 못했습니다. Enter 키 시도...")
            # Enter 키 이벤트 시도
            enter_key_script = """
            (function() {
                var searchInput = document.querySelector('#query') || 
                                 document.querySelector('input.sch_input');
                if (searchInput) {
                    var e = new KeyboardEvent('keydown', {
                        key: 'Enter',
                        code: 'Enter',
                        keyCode: 13,
                        bubbles: true
                    });
                    searchInput.dispatchEvent(e);
                    return true;
                }
                return false;
            })();
            """
            chrome_dt.execute_script(enter_key_script)
            
        time.sleep(3)

        # 4. nvmid로 검색 결과 찾기 및 클릭
        logger.info("기본 검색어 NV MID로 검색 결과 찾기")
        config_nvmid = config.NV_MID_2
        logger.info(f"찾을 NV MID: {config_nvmid}")

        # click_result_script = f"""
        # (function() {{
        #     var targetNvmid = '{config_nvmid}';
        #     var targetAriaId = 'view_type_guide_' + targetNvmid;
        #     var targetResult = null;
        #     var foundNvmid = null;
        #     var allFoundNvmids = [];  // 디버깅용
            
        #     // 요소가 나타날 때까지 대기 (최대 5초)
        #     var maxWait = 5000;
        #     var startTime = Date.now();
        #     var allLinks = [];
            
        #     // HTML 구조를 차례대로 타고 들어가면서 찾기
        #     while (targetResult === null && (Date.now() - startTime) < maxWait) {{
        #         // 1단계: .flicking-viewport 찾기
        #         var flickingViewport = document.querySelector('.flicking-viewport');
        #         console.log('1단계: flicking-viewport 존재: ' + !!flickingViewport);
                
        #         if (flickingViewport) {{
        #             // 2단계: flicking-viewport 안에서 li.ds9RptR1 찾기
        #             var listItems = flickingViewport.querySelectorAll('li.ds9RptR1');
        #             console.log('2단계: li.ds9RptR1 개수: ' + listItems.length);
                    
        #             // 3단계: 각 li를 순회하면서 a 태그 찾기
        #             for (var i = 0; i < listItems.length; i++) {{
        #                 var listItem = listItems[i];
        #                 var link = listItem.querySelector('a[aria-labelledby^="view_type_guide_"]');
                        
        #                 if (link) {{
        #                     // 4단계: aria-labelledby 속성에서 view_type_guide_ 뒤의 번호 추출
        #                     var ariaId = link.getAttribute('aria-labelledby');
        #                     console.log('3단계: 링크 ' + i + '의 aria-labelledby: ' + ariaId);
                            
        #                     if (ariaId && ariaId.startsWith('view_type_guide_')) {{
        #                         var nvmid = ariaId.replace('view_type_guide_', '');
        #                         allFoundNvmids.push(nvmid);  // 디버깅용
        #                         console.log('4단계: 추출한 NV MID: ' + nvmid + ', 찾을 NV MID: ' + targetNvmid);
                                
        #                         // 5단계: 번호가 일치하는지 확인
        #                         if (nvmid === targetNvmid) {{
        #                             targetResult = link;
        #                             foundNvmid = nvmid;
        #                             console.log('✓ NV MID 일치하는 요소 찾음! 인덱스: ' + i + ', NV MID: ' + nvmid);
        #                             break;
        #                         }}
        #                     }}
        #                 }}
        #             }}
        #         }}
                
        #         // flicking-viewport가 없거나 찾지 못한 경우, 다른 구조 시도
        #         if (!targetResult) {{
        #             // 대안: ul > li.ds9RptR1 구조 찾기
        #             var ulElements = document.querySelectorAll('ul');
        #             console.log('대안: ul 요소 개수: ' + ulElements.length);
                    
        #             for (var u = 0; u < ulElements.length; u++) {{
        #                 var ul = ulElements[u];
        #                 var listItems = ul.querySelectorAll('li.ds9RptR1');
                        
        #                 for (var i = 0; i < listItems.length; i++) {{
        #                     var listItem = listItems[i];
        #                     var link = listItem.querySelector('a[aria-labelledby^="view_type_guide_"]');
                            
        #                     if (link) {{
        #                         var ariaId = link.getAttribute('aria-labelledby');
        #                         if (ariaId && ariaId.startsWith('view_type_guide_')) {{
        #                             var nvmid = ariaId.replace('view_type_guide_', '');
        #                             allFoundNvmids.push(nvmid);
                                    
        #                             if (nvmid === targetNvmid) {{
        #                                 targetResult = link;
        #                                 foundNvmid = nvmid;
        #                                 console.log('✓ NV MID 일치하는 요소 찾음! (ul 구조) 인덱스: ' + i + ', NV MID: ' + nvmid);
        #                                 break;
        #                             }}
        #                         }}
        #                     }}
        #                 }}
                        
        #                 if (targetResult) break;
        #             }}
        #         }}
                
        #         // 여전히 찾지 못한 경우 대기
        #         if (!targetResult) {{
        #             var wait = 100;
        #             var waitUntil = Date.now() + wait;
        #             while (Date.now() < waitUntil) {{
        #                 // busy wait
        #             }}
        #         }}
        #     }}
            
        #     // 디버깅 정보 수집
        #     if (allLinks.length === 0) {{
        #         var flickingViewport = document.querySelector('.flicking-viewport');
        #         if (flickingViewport) {{
        #             var listItems = flickingViewport.querySelectorAll('li.ds9RptR1');
        #             for (var i = 0; i < listItems.length; i++) {{
        #                 var link = listItems[i].querySelector('a[aria-labelledby^="view_type_guide_"]');
        #                 if (link) {{
        #                     allLinks.push(link);
        #                 }}
        #             }}
        #         }}
        #     }}
            
        #     console.log('총 링크 개수: ' + allLinks.length);
        #     console.log('찾을 NV MID: ' + targetNvmid);
        #     console.log('찾은 요소: ' + (targetResult ? '있음' : '없음'));
            
        #     // 디버깅 정보
        #     var debugInfo = {{
        #         totalLinks: allLinks.length,
        #         targetNvmid: targetNvmid,
        #         foundNvmids: allFoundNvmids.slice(0, 20),
        #         found: targetResult !== null,
        #         matchedNvmid: foundNvmid,
        #         hasFlickingViewport: !!document.querySelector('.flicking-viewport'),
        #         hasListItems: document.querySelectorAll('li.ds9RptR1').length
        #     }};
        #     console.log('디버깅 정보:', JSON.stringify(debugInfo));
            
        #     if (targetResult) {{
        #         // 요소가 보이지 않으면 스크롤 (클릭하기 전에만)
        #         var rect = targetResult.getBoundingClientRect();
        #         var isVisible = rect.width > 0 && rect.height > 0 && 
        #                        rect.top >= 0 && rect.left >= 0 &&
        #                        rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
        #                        rect.right <= (window.innerWidth || document.documentElement.clientWidth);
                
        #         if (!isVisible) {{
        #             console.log('Element not visible, scrolling to view...');
        #             targetResult.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
        #             var scrollWait = 500;
        #             var scrollWaitUntil = Date.now() + scrollWait;
        #             while (Date.now() < scrollWaitUntil) {{
        #                 // busy wait
        #             }}
        #         }}
                
        #         // 요소가 클릭 가능한지 확인
        #         var computedStyle = window.getComputedStyle(targetResult);
        #         var isClickable = computedStyle.display !== 'none' && 
        #                          computedStyle.visibility !== 'hidden' &&
        #                          computedStyle.pointerEvents !== 'none';
                
        #         if (!isClickable) {{
        #             console.log('Element is not clickable');
        #             return {{ success: false, nvmid: foundNvmid, reason: 'not_clickable', debug: debugInfo }};
        #         }}
                
        #         console.log('Clicking product with NV MID: ' + foundNvmid);
                
        #         // 여러 방법으로 클릭 시도
        #         try {{
        #             targetResult.click();
        #         }} catch (e) {{
        #             console.log('Direct click failed, trying mouse event');
        #             try {{
        #                 var clickEvent = new MouseEvent('click', {{
        #                     view: window,
        #                     bubbles: true,
        #                     cancelable: true
        #                 }});
        #                 targetResult.dispatchEvent(clickEvent);
        #             }} catch (e2) {{
        #                 console.log('MouseEvent click failed, trying href navigation');
        #                 if (targetResult.href) {{
        #                     window.location.href = targetResult.href;
        #                 }} else {{
        #                     return {{ success: false, nvmid: foundNvmid, reason: 'click_failed', debug: debugInfo }};
        #                 }}
        #             }}
        #         }}
                
        #         return {{ success: true, nvmid: foundNvmid, debug: debugInfo }};
        #     }}
            
        #     return {{ success: false, nvmid: null, reason: 'nvmid_not_found', debug: debugInfo }};
        # }})();
        # """

        # click_result_script = create_click_result_script(config_nvmid) # 생 스크립트로 실행
        # click_result_script = chrome_dt.execute_script(create_click_result_script(config_nvmid))
        # 재시도 로직 추가
        max_retries = 1
        result = None
        for attempt in range(max_retries):
            logger.info(f"NV MID 검색 시도 {attempt + 1}/{max_retries}")
            # logger.debug(f"스크립트 길이: {len(click_result_script)} 문자")
            
            try:
                result = chrome_dt.execute_script(create_click_result_script(config_nvmid))
                # result = chrome_dt.execute_script(click_result_script)
            except Exception as e:
                logger.error(f"execute_script 실행 중 예외 발생: {e}")
                result = None
            
            if result is not None:
                logger.info(f"✓ 스크립트 실행 성공 (시도 {attempt + 1})")
                logger.debug(f"결과 타입: {type(result)}, 값: {result}")
                break
            else:
                logger.warning(f"스크립트 실행 실패 (시도 {attempt + 1}/{max_retries}) - result가 None입니다")
                if attempt < max_retries - 1:
                    time.sleep(2)  # 재시도 전 대기
                    try:
                        current_url = chrome_dt.get_current_url()
                        logger.info(f"현재 URL: {current_url}")
                    except Exception as e:
                        logger.warning(f"현재 URL 확인 실패: {e}")

        if result is None:
            logger.error("검색 결과 클릭 스크립트 실행 실패: 모든 재시도 실패")
            logger.warning("스크립트 실행 결과: None")
            # 디버깅을 위해 페이지 상태 확인
            debug_script = """
            (function() {
                var links = document.querySelectorAll('a[aria-labelledby^="view_type_guide_"]');
                return {
                    linkCount: links.length,
                    firstLinkAria: links.length > 0 ? links[0].getAttribute('aria-labelledby') : null,
                    firstLinkVisible: links.length > 0 ? (function() {
                        var rect = links[0].getBoundingClientRect();
                        return rect.width > 0 && rect.height > 0;
                    })() : false,
                    pageTitle: document.title,
                    readyState: document.readyState
                };
            })();
            """
            debug_result = chrome_dt.execute_script(debug_script)
            if debug_result:
                logger.warning(f"페이지 디버깅 정보: {debug_result}")
            # 더 이상 진행하지 않음
        else:
            logger.info(f"스크립트 실행 결과 타입: {type(result)}")
            logger.info(f"스크립트 실행 결과: {result}")
        if result and isinstance(result, dict):
            if result.get('success'):
                found_nvmid = result.get('nvmid')
                logger.info(f"✓ NV MID 일치하는 검색 결과 클릭 완료: {found_nvmid}")
                debug_info = result.get('debug', {})
                if debug_info:
                    logger.info(f"디버깅 정보 - 총 링크: {debug_info.get('totalLinks')}, 찾은 NV MID 목록: {debug_info.get('foundNvmids', [])[:10]}")
            else:
                reason = result.get('reason', 'unknown')
                debug_info = result.get('debug', {})
                logger.warning(f"NV MID 일치하는 검색 결과를 찾지 못했습니다. 이유: {reason}")
                if debug_info:
                    logger.warning(f"디버깅 정보 - 총 링크: {debug_info.get('totalLinks')}, 찾을 NV MID: {debug_info.get('targetNvmid')}, 찾은 NV MID 목록: {debug_info.get('foundNvmids', [])[:20]}")
                    logger.warning(f"flicking-viewport 존재: {debug_info.get('hasFlickingViewport')}, li.ds9RptR1 개수: {debug_info.get('hasListItems')}")
        else:
            logger.warning("검색 결과 클릭 스크립트 실행 실패")
            logger.warning(f"스크립트 실행 결과: {result}")
            # 디버깅을 위해 페이지 상태 확인
            debug_script = """
            (function() {
                var links = document.querySelectorAll('a[aria-labelledby^="view_type_guide_"]');
                return {
                    linkCount: links.length,
                    firstLinkAria: links.length > 0 ? links[0].getAttribute('aria-labelledby') : null,
                    firstLinkVisible: links.length > 0 ? (function() {
                        var rect = links[0].getBoundingClientRect();
                        return rect.width > 0 && rect.height > 0;
                    })() : false
                };
            })();
            """
            debug_result = chrome_dt.execute_script(debug_script)
            if debug_result:
                logger.info(f"디버깅 정보: 링크 개수={debug_result.get('linkCount')}, 첫 링크 aria={debug_result.get('firstLinkAria')}, 보임={debug_result.get('firstLinkVisible')}")
        
        # 광고검사 스크립트 추후 추가 
        # 같은 nvmid 없음. 광고가 붙은것 제외.
        # 광고검사 스크립트 추후 추가 
        
        time.sleep(3)
        
        # URL 변경 확인
        current_url = chrome_dt.get_current_url()
        logger.info(f"현재 URL: {current_url}")
        
        # 5. nvmid 로 이동하고 구매 추가정보 버튼 클릭
        logger.info("구매 추가정보 버튼 클릭")
        click_info_script = """
        (function() {
            // 스크롤 다운
            window.scrollTo(0, document.body.scrollHeight);
            
            // 구매 추가정보 버튼 찾기
            var infoBtn = document.querySelector('a[data-shp-area-id="info"]') ||
                         Array.from(document.querySelectorAll('a')).find(a => 
                             a.textContent.includes('구매 추가정보'));
            if (infoBtn) {
                infoBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });
                setTimeout(() => infoBtn.click(), 500);
                return true;
            }
            return false;
        })();
        """
        chrome_dt.execute_script(click_info_script)
        time.sleep(2)
        
        current_after_info_url = chrome_dt.get_current_url()
        if current_after_info_url != current_url:
            logger.info(f"구매 추가정보 버튼 클릭 성공 뒤로가기 2번 진행")
                    # CDP 네이티브 명령어로 한 번에 2번 뒤로가기
            success = chrome_dt.navigate_back_multiple(steps=2)
            time.sleep(3)
            # chrome_dt.execute_script("window.history.go(-2);")
        else:

            logger.info(f"구매 추가정보 버튼 클릭 실패 그냥 진행 ")
            time.sleep(3)

        # 6. 임시 검색어(3단계)로 재검색
        temp_search_keyword = config.TEMP_SEARCH_KEYWORD_LIST
        logger.info(f"임시 검색어 입력: {temp_search_keyword}")
        # 뒤로가기 제거하고 검색 페이지로 직접 이동
        search_script = """
        (function() {
            // 가짜 검색창 클릭
            var fakeSearch = document.querySelector('#MM_SEARCH_FAKE') ||
                            document.querySelector('.MM_search_fake') ||
                            document.querySelector('[id*="SEARCH_FAKE"]');
            
            if (fakeSearch) {
                fakeSearch.scrollIntoView({ behavior: 'smooth', block: 'center' });
                setTimeout(() => {
                    fakeSearch.click();
                }, 300);
                return true;
            }
            return false;
        })();
        """
        chrome_dt.execute_script(search_script)
        time.sleep(3)

        # 새 검색어 입력
        clear_and_search_script = f"""
        (function() {{
            var searchInput = document.querySelector('#query') || 
                             document.querySelector('input.sch_input') ||
                             document.querySelector('input[type="search"]');
            if (searchInput) {{
                searchInput.focus();
                searchInput.value = '';
                searchInput.value = '{temp_search_keyword}';
                searchInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                searchInput.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', code: 'Enter' }}));
                return true;
            }}
            return false;
        }})();
        """
        config_nvmid = config.NV_MID # 임시 id 로 체인지
        chrome_dt.execute_script(clear_and_search_script)
        time.sleep(5)  # 3초 -> 5초로 증가 (검색 결과 로딩 대기)
        chrome_dt.wait_for_load() 
        # time.sleep(3)
        
        # 7. 다시 첫 번째 결과 클릭 (동일한 스크립트 재사용)

        # result = chrome_dt.execute_script(click_result_script)
        result= chrome_dt.execute_script(create_click_result_script(config_nvmid))
        if result and isinstance(result, dict) and result.get('success'):
            nvmid = result.get('nvmid')
            if nvmid:
                logger.info(f"✓ 검색 결과 클릭 완료 (NV MID: {nvmid})")
                if nvmid == config.NV_MID:
                    logger.info(f"✓ NV MID가 config와 일치합니다: {config.NV_MID}")
                else:
                    logger.warning(f"⚠ NV MID 불일치 - 찾은 값: {nvmid}, config 값: {config.NV_MID}")
            else:
                logger.info("✓ 검색 결과 클릭 완료")
        else:
            logger.warning("검색 결과를 찾지 못했습니다.")
        time.sleep(3)


        # 8. 다시 구매 추가정보 버튼 클릭
        chrome_dt.execute_script(click_info_script)
        time.sleep(2)
        
        logger.info(f"크롤링 작업 완료 - 반복: {iteration:02d}")
        return True
        
    except Exception as e:
        logger.error(f"크롤링 중 오류 발생: {e}", exc_info=True)
        return False


def test_mobile_chrome_crawling_cdtp(
    restart_chrome_each_iteration=True,
    enable_airplane_mode_on_chrome_start=True
):
    """
    휴대폰 Chrome 직접 제어 크롤링 테스트 (Chrome DevTools Protocol 사용)
    
    Args:
        restart_chrome_each_iteration: 각 반복마다 Chrome을 재시작할지 여부
        enable_airplane_mode_on_chrome_start: Chrome 시작 시 비행기 모드 켰다 끄기 여부 (IP 변경용)
    """
    config = Config()
    logger.info("=" * 70)
    logger.info("휴대폰 Chrome 직접 제어 크롤링 테스트 (Chrome DevTools Protocol)")
    logger.info("=" * 70)
    logger.info(f"메인 키워드: {config.MAIN_KEYWORD_LIST}")
    logger.info(f"기본 검색 키워드: {config.BASE_SEARCH_KEYWORD_LIST}")
    logger.info(f"반복 횟수: {config.REPEAT_COUNT}")
    logger.info(f"NV MID: {config.NV_MID}")
    logger.info(f"Chrome 재시작: {'매 반복마다' if restart_chrome_each_iteration else '사용 안함'}")
    logger.info(f"비행기 모드: {'크롬 시작 시 켰다 끄기 (IP 변경용)' if enable_airplane_mode_on_chrome_start else '사용 안함'}")


    logger.info("=" * 70)
    
    # ADB Manager 초기화 (test3.py 방식)
    adb = get_adb_manager()
    
    # ADB 연결 확인
    if not adb.check_connection():
        logger.error("⚠ ADB 연결 실패. 테스트를 중단합니다.")
        logger.error("휴대폰이 USB로 연결되어 있고 USB 디버깅이 활성화되어 있는지 확인하세요.")
        return False
    
    # 포트 포워딩 설정
    logger.info("\n포트 포워딩 설정 중...")
    if not setup_port_forwarding(adb, config.REMOTE_DEBUGGING_PORT):
        logger.error("포트 포워딩 설정 실패. 테스트를 중단합니다.")
        return False
    
    # 네이버 모바일 URL
    naver_url = config.NAVER_MOBILE_URL if hasattr(config, 'NAVER_MOBILE_URL') else None
    
    # Chrome DevTools 클라이언트 초기화
    chrome_dt = ChromeDevTools(port=config.REMOTE_DEBUGGING_PORT)
    
    # 반복 테스트
    success_count = 0

   # 여기에 반복 테스트 로직이 들어가야 합니다
    # 예: for iteration in range(config.REPEAT_COUNT):
    #         ...
    
    # Chrome DevTools 연결 종료
    if chrome_dt:
        chrome_dt.close()
    
    # 최종 결과
    logger.info("\n" + "=" * 70)
    logger.info("테스트 완료")
    logger.info(f"성공: {success_count}/{config.REPEAT_COUNT}")
    logger.info("=" * 70)
    
    return success_count == config.REPEAT_COUNT


def main():
    """메인 함수"""
    restart_each_iteration = True  # True: 매번 재시작, False: 재시작 안함
    # enable_airplane_mode_on_chrome_start = True  # True: Chrome 시작 시 비행기 모드 켰다 끄기 (IP 변경용)
    
    test_mobile_chrome_crawling_cdtp(
        restart_chrome_each_iteration=restart_each_iteration,
        # enable_airplane_mode_on_chrome_start=enable_airplane_mode_on_chrome_start
    )


if __name__ == '__main__':
    main()
