"""
SSH 터널(SOCKS Proxy)을 통한 로컬 크롤러
- 내 PC에서 Python 코드 실행
- SSH 터널로 상대방 서버(화이트리스트 IP)에 연결
- 모든 크롤링 트래픽이 상대방 서버 IP로 전송됨
"""
import time
import logging
import random
import threading
import queue
import subprocess
import os
import signal
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# SSH 터널 관리 클래스
# ============================================================================
# SOCKS5 Proxy 사용 SOCKS5 Proxy는 TCP 포트 1080 보통

class SSHTunnelManager:
    """
    SSH 터널(SOCKS Proxy) 관리
    - 상대방 서버로 SSH 연결 + SOCKS 프록시 생성
    - 자동 재연결
    """
    
    def __init__(self, config_file='ssh_servers.txt'):
        """
        Args:
            config_file: SSH 서버 설정 파일
                형식: server_ip,ssh_port,username,ssh_key_path,socks_port (한 줄에 하나)
                예: 192.168.1.100,22,user1,~/.ssh/id_rsa,9050
        """
        self.servers = []
        self.tunnels = {}  # {socks_port: {'process': subprocess, 'server_info': {...}}}
        self.lock = threading.Lock()
        self._load_config(config_file)
    
    def _load_config(self, config_file):
        """SSH 서버 설정 로드"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split(',')
                        if len(parts) >= 5:
                            self.servers.append({
                                'server_ip': parts[0],
                                'ssh_port': parts[1],
                                'username': parts[2],
                                'ssh_key': os.path.expanduser(parts[3]),  # ~/.ssh/id_rsa 확장
                                'socks_port': int(parts[4])
                            })
            logger.info(f"SSH 서버 설정 로드 완료: {len(self.servers)}개 서버")
            
            if len(self.servers) == 0:
                raise Exception("사용 가능한 SSH 서버가 없습니다")
                
        except Exception as e:
            logger.error(f"SSH 서버 설정 로드 실패: {e}")
            raise
    
    def create_tunnel(self, server_index=0):
        """
        SSH 터널 생성 (SOCKS Proxy)
        
        Args:
            server_index: 서버 인덱스 (기본값: 0)
        
        Returns:
            dict: 터널 정보 {'socks_port': int, 'server_ip': str} 또는 None
        """
        if server_index >= len(self.servers):
            logger.error(f"잘못된 서버 인덱스: {server_index}")
            return None
        
        server = self.servers[server_index]
        socks_port = server['socks_port']
        
        try:
            # 이미 터널이 존재하는지 확인
            with self.lock:
                if socks_port in self.tunnels:
                    logger.info(f"터널이 이미 존재합니다: SOCKS 포트 {socks_port}")
                    return {
                        'socks_port': socks_port,
                        'server_ip': server['server_ip']
                    }
            
            # SSH 터널 명령어 생성
            # -D: SOCKS 프록시 생성
            # -N: 명령 실행 없이 포트 포워딩만
            # -f: 백그라운드 실행
            # -C: 압축
            ssh_cmd = [
                'ssh',
                '-D', str(socks_port),  # SOCKS 프록시 포트
                '-N',  # 명령 실행 없음
                '-C',  # 압축
                '-f',  # 백그라운드
                '-o', 'StrictHostKeyChecking=no',  # 호스트 키 확인 생략
                '-o', 'ServerAliveInterval=60',  # 연결 유지
                '-o', 'ServerAliveCountMax=3',
                '-p', server['ssh_port'],
                '-i', server['ssh_key'],  # SSH 키 파일
                f"{server['username']}@{server['server_ip']}"
            ]
            
            logger.info(f"SSH 터널 생성 중...")
            logger.info(f"  서버: {server['server_ip']}:{server['ssh_port']}")
            logger.info(f"  사용자: {server['username']}")
            logger.info(f"  SOCKS 포트: {socks_port}")
            
            # SSH 터널 시작
            process = subprocess.Popen(
                ssh_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # SSH 터널이 제대로 시작될 때까지 대기
            time.sleep(3)
            
            # 프로세스가 살아있는지 확인
            if process.poll() is not None:
                # 프로세스가 죽었으면 에러 로그 출력
                stdout, stderr = process.communicate()
                logger.error(f"SSH 터널 생성 실패:")
                logger.error(f"  stdout: {stdout.decode()}")
                logger.error(f"  stderr: {stderr.decode()}")
                return None
            
            # 터널 정보 저장
            with self.lock:
                self.tunnels[socks_port] = {
                    'process': process,
                    'server_info': server
                }
            
            logger.info(f"✓ SSH 터널 생성 완료: localhost:{socks_port} → {server['server_ip']}")
            
            # 터널 작동 확인
            if self._verify_tunnel(socks_port, server['server_ip']):
                logger.info(f"✓ SSH 터널 작동 확인 완료")
                return {
                    'socks_port': socks_port,
                    'server_ip': server['server_ip']
                }
            else:
                logger.warning(f"⚠ SSH 터널 작동 확인 실패 (계속 진행)")
                return {
                    'socks_port': socks_port,
                    'server_ip': server['server_ip']
                }
            
        except Exception as e:
            logger.error(f"SSH 터널 생성 실패: {e}", exc_info=True)
            return None
    
    def _verify_tunnel(self, socks_port, expected_ip):
        """
        SSH 터널이 제대로 작동하는지 확인
        
        Args:
            socks_port: SOCKS 프록시 포트
            expected_ip: 예상되는 서버 IP
        
        Returns:
            bool: 작동 여부
        """
        try:
            import requests
            
            # SOCKS 프록시를 통해 IP 확인
            proxies = {
                'http': f'socks5://127.0.0.1:{socks_port}',
                'https': f'socks5://127.0.0.1:{socks_port}'
            }
            
            response = requests.get(
                'https://api.ipify.org?format=json',
                proxies=proxies,
                timeout=10
            )
            
            if response.status_code == 200:
                current_ip = response.json().get('ip')
                logger.info(f"  현재 IP (터널 경유): {current_ip}")
                
                if current_ip == expected_ip:
                    logger.info(f"  ✓ IP 일치 확인!")
                else:
                    logger.warning(f"  ⚠ IP 불일치: 예상={expected_ip}, 실제={current_ip}")
                    logger.warning(f"    (NAT/프록시가 있을 수 있습니다)")
                
                return True
            else:
                logger.error(f"  ✗ IP 확인 실패: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"  ✗ 터널 검증 실패: {e}")
            return False
    
    def close_tunnel(self, socks_port):
        """SSH 터널 종료"""
        try:
            with self.lock:
                if socks_port in self.tunnels:
                    tunnel = self.tunnels[socks_port]
                    
                    # 프로세스 종료
                    try:
                        tunnel['process'].terminate()
                        tunnel['process'].wait(timeout=5)
                    except:
                        try:
                            tunnel['process'].kill()
                        except:
                            pass
                    
                    del self.tunnels[socks_port]
                    logger.info(f"SSH 터널 종료: SOCKS 포트 {socks_port}")
        except Exception as e:
            logger.error(f"SSH 터널 종료 실패: {e}")
    
    def close_all_tunnels(self):
        """모든 SSH 터널 종료"""
        logger.info("모든 SSH 터널 종료 중...")
        with self.lock:
            for socks_port in list(self.tunnels.keys()):
                self.close_tunnel(socks_port)
        logger.info("모든 SSH 터널 종료 완료")


# ============================================================================
# Chrome 인스턴스 관리 (SSH 터널 사용)
# ============================================================================

class TunnelChromeManager:
    """
    SSH 터널을 사용하는 Chrome 인스턴스 관리
    - 각 Chrome이 SSH 터널(SOCKS Proxy)을 통해 통신
    """
    
    def __init__(self, max_instances=5, headless=False):
        """
        Args:
            max_instances: 최대 인스턴스 수
            headless: Headless 모드 (기본값: False, 로컬에서는 GUI 보는 게 편함)
        """
        self.max_instances = max_instances
        self.headless = headless
        self.instances = {}
        self.available_ids = queue.Queue()
        self.lock = threading.Lock()
        
        for i in range(max_instances):
            self.available_ids.put(i + 1)
        
        logger.info(f"Chrome 인스턴스 매니저 초기화 (최대: {max_instances}, Headless: {headless})")
    
    def create_instance(self, tunnel_info):
        """
        SSH 터널을 사용하는 Chrome 인스턴스 생성
        
        Args:
            tunnel_info: 터널 정보 {'socks_port': int, 'server_ip': str}
        
        Returns:
            tuple: (driver, instance_id) 또는 (None, None)
        """
        try:
            instance_id = self.available_ids.get(timeout=5)
            
            # Chrome 옵션 설정
            options = ChromeOptions()
            
            # 🔑 핵심: SOCKS 프록시 설정
            socks_port = tunnel_info['socks_port']
            options.add_argument(f'--proxy-server=socks5://127.0.0.1:{socks_port}')
            
            # 추가 옵션
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # Headless 모드 (선택사항)
            if self.headless:
                options.add_argument('--headless=new')
                options.add_argument('--disable-gpu')
                options.add_argument('--window-size=1920,1080')
            
            # 스텔스 설정
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # 각 인스턴스별 독립적인 사용자 데이터
            user_data_dir = f"chrome_data_{instance_id}"
            options.add_argument(f'--user-data-dir={user_data_dir}')
            
            # WebDriver 생성
            service = Service()
            driver = webdriver.Chrome(service=service, options=options)
            
            # 스텔스 스크립트 주입
            self._inject_stealth_scripts(driver)
            
            with self.lock:
                self.instances[instance_id] = {
                    'driver': driver,
                    'tunnel_info': tunnel_info,
                    'user_data_dir': user_data_dir
                }
            
            logger.info(f"✓ Chrome 인스턴스 생성 완료: ID {instance_id}, 터널 포트 {socks_port}")
            
            # IP 확인 (디버깅용)
            try:
                driver.get('https://api.ipify.org?format=json')
                time.sleep(2)
                page_source = driver.page_source
                if tunnel_info['server_ip'] in page_source:
                    logger.info(f"  ✓ Chrome이 서버 IP {tunnel_info['server_ip']}를 사용 중")
                else:
                    logger.warning(f"  ⚠ IP 확인 필요 (페이지 소스 확인)")
            except Exception as e:
                logger.warning(f"  IP 확인 중 오류: {e}")
            
            return driver, instance_id
            
        except queue.Empty:
            logger.error("사용 가능한 인스턴스 ID가 없습니다")
            return None, None
        except Exception as e:
            logger.error(f"Chrome 인스턴스 생성 실패: {e}", exc_info=True)
            if 'instance_id' in locals():
                self.available_ids.put(instance_id)
            return None, None
    
    def _inject_stealth_scripts(self, driver):
        """봇 탐지 회피 스크립트"""
        stealth_js = """
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        window.navigator.chrome = {runtime: {}, loadTimes: function() {}, csi: function() {}, app: {}};
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        Object.defineProperty(navigator, 'languages', {get: () => ['ko-KR', 'ko', 'en-US', 'en']});
        """
        try:
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': stealth_js})
        except:
            try:
                driver.execute_script(stealth_js)
            except:
                pass
    
    def release_instance(self, instance_id):
        """Chrome 인스턴스 해제"""
        try:
            with self.lock:
                if instance_id in self.instances:
                    instance = self.instances[instance_id]
                    
                    try:
                        instance['driver'].quit()
                    except:
                        pass
                    
                    del self.instances[instance_id]
                    self.available_ids.put(instance_id)
                    logger.info(f"Chrome 인스턴스 해제: ID {instance_id}")
        except Exception as e:
            logger.error(f"Chrome 인스턴스 해제 실패: {e}")


# ============================================================================
# 병렬 크롤러
# ============================================================================

class SSHTunnelCrawler:
    """SSH 터널을 통한 병렬 크롤러"""
    
    def __init__(self, max_workers=5, ssh_config='ssh_servers.txt', headless=False):
        """
        Args:
            max_workers: 동시 실행할 최대 작업 수
            ssh_config: SSH 서버 설정 파일
            headless: Headless 모드 사용 여부
        """
        self.tunnel_manager = SSHTunnelManager(ssh_config)
        self.chrome_manager = TunnelChromeManager(max_instances=max_workers, headless=headless)
        self.max_workers = max_workers
        self.tunnel_info = None
        
        # SSH 터널 생성 (모든 인스턴스가 공유)
        logger.info("SSH 터널 생성 중...")
        self.tunnel_info = self.tunnel_manager.create_tunnel(server_index=0)
        
        if not self.tunnel_info:
            raise Exception("SSH 터널 생성 실패")
        
        logger.info(f"✓ SSH 터널 크롤러 초기화 완료 (최대 작업: {max_workers})")
    
    def crawl_task(self, row_data, task_id):
        """단일 크롤링 작업"""
        driver = None
        instance_id = None
        
        try:
            # Chrome 인스턴스 생성 (SSH 터널 사용)
            driver, instance_id = self.chrome_manager.create_instance(self.tunnel_info)
            
            if not driver:
                logger.error(f"[작업 {task_id}] Chrome 인스턴스 생성 실패")
                return {'success': False, 'task_id': task_id, 'error': 'Chrome 생성 실패'}
            
            logger.info(f"[작업 {task_id}] 크롤링 시작 (인스턴스 ID: {instance_id})")
            
            # 네이버 접속
            driver.get("https://m.naver.com")
            time.sleep(random.uniform(2, 4))
            
            # 메인 키워드 검색
            self._search_keyword(driver, row_data['main_keyword'])
            time.sleep(random.uniform(1, 2))
            
            # 새 검색어로 검색
            self._search_keyword(driver, row_data['base_search_keyword'])
            time.sleep(random.uniform(1, 2))
            
            # 상품 클릭
            self._click_by_nvmid(driver, str(row_data['nv_mid']))
            time.sleep(random.uniform(2, 3))
            
            logger.info(f"✓ [작업 {task_id}] 크롤링 완료")
            
            return {
                'success': True,
                'task_id': task_id,
                'server_ip': self.tunnel_info['server_ip'],
                'instance_id': instance_id
            }
            
        except Exception as e:
            logger.error(f"✗ [작업 {task_id}] 크롤링 실패: {e}", exc_info=True)
            return {'success': False, 'task_id': task_id, 'error': str(e)}
            
        finally:
            if instance_id:
                self.chrome_manager.release_instance(instance_id)
    
    def _search_keyword(self, driver, keyword):
        """키워드 검색"""
        try:
            search_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='search'], input.search_input"))
            )
            search_input.clear()
            
            for char in keyword:
                search_input.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))
            
            time.sleep(random.uniform(0.3, 0.8))
            
            try:
                search_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit'], .btn_search")
                search_btn.click()
            except:
                from selenium.webdriver.common.keys import Keys
                search_input.send_keys(Keys.RETURN)
            
            time.sleep(random.uniform(2, 4))
        except Exception as e:
            logger.error(f"검색 실패: {e}")
    
    def _click_by_nvmid(self, driver, nvmid):
        """nvmid로 상품 클릭"""
        click_script = f"""
        (function() {{
            var links = document.querySelectorAll('a[href*="nv_mid={nvmid}"]');
            if (links.length > 0) {{
                links[0].scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                setTimeout(() => links[0].click(), 500);
                return {{success: true, nvmid: '{nvmid}'}};
            }}
            return {{success: false, reason: 'not found'}};
        }})();
        """
        result = driver.execute_script(click_script)
        return result.get('success', False)
    
    def run_parallel(self, data_file='keyword_data.csv'):
        """병렬 크롤링 실행"""
        try:
            # CSV 로드
            encodings = ['cp949', 'euc-kr', 'utf-8', 'latin-1']
            df = None
            
            for encoding in encodings:
                try:
                    df = pd.read_csv(data_file, encoding=encoding)
                    logger.info(f"CSV 로드 성공 (인코딩: {encoding}): {len(df)}개 행")
                    break
                except:
                    continue
            
            if df is None:
                logger.error("CSV 파일을 읽을 수 없습니다")
                return
            
            # 병렬 실행
            results = []
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = []
                
                for idx, row in df.iterrows():
                    future = executor.submit(self.crawl_task, row, idx + 1)
                    futures.append(future)
                
                for future in as_completed(futures):
                    try:
                        result = future.result(timeout=300)
                        results.append(result)
                        
                        if result['success']:
                            logger.info(f"✓ 작업 {result['task_id']} 성공 (서버 IP: {result['server_ip']})")
                        else:
                            logger.warning(f"✗ 작업 {result['task_id']} 실패: {result.get('error')}")
                    except Exception as e:
                        logger.error(f"작업 결과 수집 실패: {e}")
            
            success_count = sum(1 for r in results if r.get('success'))
            logger.info(f"\n{'='*50}")
            logger.info(f"크롤링 완료: {success_count}/{len(results)} 성공")
            logger.info(f"{'='*50}")
            
        except Exception as e:
            logger.error(f"병렬 크롤링 실패: {e}", exc_info=True)
        finally:
            # SSH 터널 종료
            self.tunnel_manager.close_all_tunnels()


# ============================================================================
# 메인 실행
# ============================================================================

def main():
    """메인 함수"""
    logger.info("=" * 50)
    logger.info("SSH 터널 기반 크롤러 시작")
    logger.info("=" * 50)
    
    # SSH 서버 설정 파일 예시
    ssh_example = """# SSH 서버 설정 파일
# 형식: server_ip,ssh_port,username,ssh_key_path,socks_port
# 
# ⚠️ 중요:
# 1. 내 IP가 상대방 서버에 화이트리스트로 등록되어야 합니다
# 2. SSH 키 기반 인증이 설정되어 있어야 합니다
# 3. 상대방 서버의 IP가 타겟 사이트에서 허용되어야 합니다
#
# SSH 키 생성 방법:
#   ssh-keygen -t rsa -b 4096 -C "your_email@example.com"
#   ssh-copy-id -i ~/.ssh/id_rsa.pub username@server_ip
#
# 예시:
192.168.1.100,22,user1,~/.ssh/id_rsa,9050
"""
    
    if not os.path.exists('ssh_servers.txt'):
        with open('ssh_servers.txt', 'w', encoding='utf-8') as f:
            f.write(ssh_example)
        logger.info("=" * 50)
        logger.info("⚠️  SSH 서버 설정 파일이 생성되었습니다: ssh_servers.txt")
        logger.info("=" * 50)
        logger.info("\n다음 단계:")
        logger.info("1. 상대방 서버에 SSH 접근 권한 요청")
        logger.info("2. SSH 키 생성 및 상대방 서버에 등록")
        logger.info("3. ssh_servers.txt 파일에 실제 서버 정보 입력")
        logger.info("4. 다시 실행")
        logger.info("\nSSH 터널 테스트:")
        logger.info("  ssh -D 9050 -N -C user@server_ip")
        logger.info("  curl --socks5 127.0.0.1:9050 https://api.ipify.org")
        logger.info("=" * 50)
        return
    
    if not os.path.exists('keyword_data.csv'):
        logger.error("keyword_data.csv 파일이 없습니다")
        return
    
    try:
        # SSH 터널 크롤러 실행
        crawler = SSHTunnelCrawler(
            max_workers=5,
            ssh_config='ssh_servers.txt',
            headless=False  # GUI 보면서 디버깅 (True로 바꾸면 백그라운드)
        )
        crawler.run_parallel('keyword_data.csv')
        
    except Exception as e:
        logger.error(f"실행 실패: {e}", exc_info=True)


if __name__ == '__main__':
    main()