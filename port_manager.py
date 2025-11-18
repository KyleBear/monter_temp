"""
포트 관리 유틸리티
포트를 사용하는 프로세스를 확인하고 강제 종료하는 기능 제공
"""
import subprocess
import platform
import time
import logging
import socket

logger = logging.getLogger(__name__)


class PortManager:
    """포트 관리 클래스"""
    
    def __init__(self):
        self.system = platform.system()
    
    def get_port_process_info(self, port):
        """
        특정 포트를 사용하는 프로세스 정보 조회
        
        Args:
            port: 포트 번호
        
        Returns:
            dict: 프로세스 정보 (pid, name, command) 또는 None
        """
        try:
            if self.system == 'Windows':
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
            
            elif self.system in ['Linux', 'Darwin']:  # Linux or macOS
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
    
    def check_port_in_use(self, port):
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
    
    def kill_process_by_pid(self, pid, force=True):
        """
        PID로 프로세스 종료
        
        Args:
            pid: 프로세스 ID
            force: 강제 종료 여부
        
        Returns:
            bool: 성공 여부
        """
        try:
            if self.system == 'Windows':
                # Windows: taskkill 사용
                if force:
                    result = subprocess.run(
                        ['taskkill', '/F', '/PID', str(pid)],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                else:
                    result = subprocess.run(
                        ['taskkill', '/PID', str(pid)],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                
                if result.returncode == 0:
                    logger.info(f"✓ 프로세스 종료 성공 (PID: {pid})")
                    return True
                else:
                    error_msg = result.stderr if result.stderr else result.stdout
                    logger.warning(f"프로세스 종료 실패 (PID: {pid}): {error_msg}")
                    return False
            
            elif self.system in ['Linux', 'Darwin']:
                # Linux/macOS: kill 사용
                signal = '-9' if force else '-15'
                result = subprocess.run(
                    ['kill', signal, str(pid)],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    logger.info(f"✓ 프로세스 종료 성공 (PID: {pid})")
                    return True
                else:
                    error_msg = result.stderr if result.stderr else result.stdout
                    logger.warning(f"프로세스 종료 실패 (PID: {pid}): {error_msg}")
                    return False
            
            return False
        except Exception as e:
            logger.error(f"프로세스 종료 중 오류 (PID: {pid}): {e}")
            return False
    
    def kill_process_by_name(self, process_name, force=True):
        """
        프로세스 이름으로 프로세스 종료
        
        Args:
            process_name: 프로세스 이름 (예: 'chrome.exe', 'python.exe')
            force: 강제 종료 여부
        
        Returns:
            int: 종료된 프로세스 수
        """
        killed_count = 0
        try:
            if self.system == 'Windows':
                # Windows: taskkill 사용
                if force:
                    result = subprocess.run(
                        ['taskkill', '/F', '/IM', process_name],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                else:
                    result = subprocess.run(
                        ['taskkill', '/IM', process_name],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                
                if result.returncode == 0:
                    # 출력에서 종료된 프로세스 수 파싱
                    output = result.stdout
                    for line in output.split('\n'):
                        if '프로세스' in line or 'process' in line.lower():
                            # "프로세스(PID: 1234)가 종료되었습니다." 형식 파싱
                            try:
                                # 간단히 "종료되었습니다" 또는 "terminated"가 포함된 줄 수 세기
                                if '종료' in line or 'terminated' in line.lower():
                                    killed_count += 1
                            except:
                                pass
                    logger.info(f"✓ 프로세스 종료 성공 ({process_name}): {killed_count}개")
                else:
                    error_msg = result.stderr if result.stderr else result.stdout
                    logger.warning(f"프로세스 종료 실패 ({process_name}): {error_msg}")
            
            elif self.system in ['Linux', 'Darwin']:
                # Linux/macOS: pkill 사용
                signal = '-9' if force else '-15'
                result = subprocess.run(
                    ['pkill', signal, process_name],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    logger.info(f"✓ 프로세스 종료 성공 ({process_name})")
                    killed_count = 1  # pkill은 개수를 반환하지 않음
                else:
                    error_msg = result.stderr if result.stderr else result.stdout
                    logger.warning(f"프로세스 종료 실패 ({process_name}): {error_msg}")
            
            return killed_count
        except Exception as e:
            logger.error(f"프로세스 종료 중 오류 ({process_name}): {e}")
            return killed_count
    
    def free_port(self, port, force=True, wait_time=2):
        """
        포트를 해제 (포트를 사용하는 프로세스 종료)
        
        Args:
            port: 포트 번호
            force: 강제 종료 여부
            wait_time: 프로세스 종료 후 대기 시간 (초)
        
        Returns:
            bool: 포트 해제 성공 여부
        """
        logger.info(f"[포트 해제] 포트 {port} 해제 시도 중...")
        
        # 포트 사용 여부 확인
        if not self.check_port_in_use(port):
            logger.info(f"[포트 해제] 포트 {port}는 이미 사용 중이 아닙니다.")
            return True
        
        # 포트를 사용하는 프로세스 정보 조회
        process_info = self.get_port_process_info(port)
        
        if not process_info:
            logger.warning(f"[포트 해제] 포트 {port}를 사용하는 프로세스 정보를 가져올 수 없습니다.")
            logger.warning(f"[포트 해제] 포트 {port}는 사용 중이지만 프로세스를 식별할 수 없습니다.")
            return False
        
        pid = process_info['pid']
        process_name = process_info['name']
        command = process_info['command']
        
        logger.info(f"[포트 해제] 포트 {port}를 사용하는 프로세스 발견:")
        logger.info(f"  - PID: {pid}")
        logger.info(f"  - 프로세스 이름: {process_name}")
        logger.info(f"  - 명령줄: {command}")
        
        # 프로세스 종료
        logger.info(f"[포트 해제] 프로세스 종료 시도 중... (PID: {pid})")
        success = self.kill_process_by_pid(pid, force=force)
        
        if success:
            # 프로세스 종료 후 대기
            logger.info(f"[포트 해제] 프로세스 종료 완료. {wait_time}초 대기 중...")
            time.sleep(wait_time)
            
            # 포트 해제 확인
            if not self.check_port_in_use(port):
                logger.info(f"✓ [포트 해제] 포트 {port} 해제 완료")
                return True
            else:
                logger.warning(f"[포트 해제] 프로세스를 종료했지만 포트 {port}가 여전히 사용 중입니다.")
                # 다시 프로세스 정보 확인
                new_process_info = self.get_port_process_info(port)
                if new_process_info:
                    logger.warning(f"[포트 해제] 새로운 프로세스가 포트를 사용 중입니다:")
                    logger.warning(f"  - PID: {new_process_info['pid']}")
                    logger.warning(f"  - 프로세스 이름: {new_process_info['name']}")
                return False
        else:
            logger.error(f"✗ [포트 해제] 포트 {port} 해제 실패 (프로세스 종료 실패)")
            return False
    
    def free_ports(self, ports, force=True, wait_time=2):
        """
        여러 포트를 한번에 해제
        
        Args:
            ports: 포트 번호 리스트
            force: 강제 종료 여부
            wait_time: 프로세스 종료 후 대기 시간 (초)
        
        Returns:
            dict: {포트: 성공여부} 딕셔너리
        """
        results = {}
        for port in ports:
            results[port] = self.free_port(port, force=force, wait_time=wait_time)
        return results
    
    def get_all_listening_ports(self):
        """
        모든 리스닝 포트 목록 가져오기
        
        Returns:
            list: 포트 번호 리스트
        """
        ports = []
        try:
            if self.system == 'Windows':
                result = subprocess.run(
                    ['netstat', '-ano'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if 'LISTENING' in line and '127.0.0.1:' in line:
                            parts = line.split()
                            for part in parts:
                                if '127.0.0.1:' in part:
                                    try:
                                        port = int(part.split(':')[1])
                                        if port not in ports:
                                            ports.append(port)
                                    except:
                                        pass
            
            elif self.system in ['Linux', 'Darwin']:
                result = subprocess.run(
                    ['lsof', '-i', '-P', '-n'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if 'LISTEN' in line:
                            parts = line.split()
                            if len(parts) >= 9:
                                addr = parts[8]
                                if ':' in addr:
                                    try:
                                        port = int(addr.split(':')[1])
                                        if port not in ports:
                                            ports.append(port)
                                    except:
                                        pass
            
            return sorted(ports)
        except Exception as e:
            logger.error(f"리스닝 포트 목록 조회 실패: {e}")
            return []


if __name__ == '__main__':
    # 테스트 코드
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    manager = PortManager()
    
    # 테스트할 포트
    test_ports = [9222, 9223]
    
    print("=" * 50)
    print("포트 관리 유틸리티 테스트")
    print("=" * 50)
    
    for port in test_ports:
        print(f"\n포트 {port} 상태 확인:")
        if manager.check_port_in_use(port):
            print(f"  - 포트 {port}는 사용 중입니다.")
            process_info = manager.get_port_process_info(port)
            if process_info:
                print(f"  - PID: {process_info['pid']}")
                print(f"  - 프로세스 이름: {process_info['name']}")
                print(f"  - 명령줄: {process_info['command']}")
        else:
            print(f"  - 포트 {port}는 사용 중이 아닙니다.")
    
    # 포트 해제 예제 (주석 처리)
    # print("\n포트 해제 예제:")
    # for port in test_ports:
    #     manager.free_port(port, force=True)

