"""
Selenium 스텔스 모드 유틸리티
봇 감지를 우회하기 위한 다양한 기법을 제공합니다.
"""
import time
import random
import logging
import json
from typing import Optional, Dict, Any
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import os
logger = logging.getLogger(__name__)


class StealthMode:
    """Selenium 스텔스 모드 클래스"""
    
    def __init__(self, driver: webdriver.Chrome):
        """
        Args:
            driver: Selenium WebDriver 인스턴스
        """
        self.driver = driver
        self.user_agents = [
            'Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            'Mozilla/5.0 (Linux; Android 11; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            'Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
        ]
    
    def apply_stealth_options(self, chrome_options: Options, use_remote_device: bool = True) -> Options:
        """
        Chrome 옵션에 스텔스 모드 설정 적용
        
        Args:
            chrome_options: Chrome Options 인스턴스
            use_remote_device: 원격 디바이스 사용 여부 (True일 때 일부 옵션 제외)
        
        Returns:
            수정된 Chrome Options
        """
        # 원격 디바이스를 사용할 때는 최소한의 옵션만 적용
        # debuggerAddress를 사용하면 이미 실행 중인 Chrome에 연결하므로
        # 대부분의 옵션이 무시되거나 충돌할 수 있음
        if use_remote_device:
            # 원격 디바이스에서는 debuggerAddress만 설정하고 다른 옵션은 추가하지 않음
            # 이미 실행 중인 Chrome에는 옵션을 적용할 수 없음
            logger.debug("원격 디바이스 모드: stealth 옵션 건너뜀 (debuggerAddress만 사용)")
            return chrome_options
        
        # 로컬 Chrome 사용 시에만 모든 스텔스 옵션 적용
        # 기본 봇 감지 우회 옵션
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        
        # 원격 디바이스가 아닐 때만 excludeSwitches 사용 (원격 디바이스에서 파싱 오류 발생)
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # 추가 우회 옵션
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-software-rasterizer')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-plugins-discovery')
        chrome_options.add_argument('--disable-default-apps')
        
        # 세션 및 캐시
        chrome_options.add_argument('--disable-application-cache')
        chrome_options.add_argument('--disable-cache')
        
        # 보안 우회
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--disable-features=IsolateOrigins,site-per-process')
        chrome_options.add_argument('--disable-site-isolation-trials')
        
        # 언어 설정
        chrome_options.add_argument('--lang=ko-KR')
        
        # 원격 디바이스가 아닐 때만 prefs 사용 (원격 디바이스에서 파싱 오류 발생)
        chrome_options.add_experimental_option('prefs', {
            'intl.accept_languages': 'ko-KR,ko,en-US,en',
            'profile.default_content_setting_values.notifications': 2,
            'profile.default_content_settings.popups': 0,
            'profile.managed_default_content_settings.images': 1,
        })
        
        # 랜덤 User-Agent 설정
        user_agent = random.choice(self.user_agents)
        chrome_options.add_argument(f'--user-agent={user_agent}')
        logger.debug(f"User-Agent 설정: {user_agent}")
        
        return chrome_options
    
    def inject_stealth_scripts(self):
        """
        CDP를 사용하여 페이지 로드 전에 탐지 방지 스크립트 주입
        """
        try:
            # WebDriver 속성 숨기기
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    // WebDriver 속성 완전히 제거
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    
                    // Chrome 객체 추가
                    window.navigator.chrome = {
                        runtime: {},
                        loadTimes: function() {},
                        csi: function() {},
                        app: {}
                    };
                    
                    // Plugins 속성 추가
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => {
                            const plugins = [];
                            for (let i = 0; i < 5; i++) {
                                plugins.push({
                                    0: {type: 'application/x-google-chrome-pdf', suffixes: 'pdf', description: 'Portable Document Format'},
                                    description: 'Portable Document Format',
                                    filename: 'internal-pdf-viewer',
                                    length: 1,
                                    name: 'Chrome PDF Plugin'
                                });
                            }
                            return plugins;
                        }
                    });
                    
                    // Languages 속성 설정
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['ko-KR', 'ko', 'en-US', 'en']
                    });
                    
                    // Permissions API 오버라이드
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                            Promise.resolve({ state: Notification.permission }) :
                            originalQuery(parameters)
                    );
                    
                    // WebGL Vendor/Renderer 랜덤화
                    const getParameter = WebGLRenderingContext.prototype.getParameter;
                    WebGLRenderingContext.prototype.getParameter = function(parameter) {
                        if (parameter === 37445) {
                            // UNMASKED_VENDOR_WEBGL
                            const vendors = ['Intel Inc.', 'Google Inc. (NVIDIA)', 'Qualcomm', 'ARM'];
                            return vendors[Math.floor(Math.random() * vendors.length)];
                        }
                        if (parameter === 37446) {
                            // UNMASKED_RENDERER_WEBGL
                            const renderers = [
                                'Intel Iris OpenGL Engine',
                                'ANGLE (NVIDIA, NVIDIA GeForce GTX 1060 Direct3D11 vs_5_0 ps_5_0, D3D11)',
                                'Adreno (TM) 640',
                                'Mali-G78 MP24'
                            ];
                            return renderers[Math.floor(Math.random() * renderers.length)];
                        }
                        return getParameter.apply(this, arguments);
                    };
                    
                    // Canvas 핑거프린팅 우회 (노이즈 추가)
                    const getImageData = CanvasRenderingContext2D.prototype.getImageData;
                    CanvasRenderingContext2D.prototype.getImageData = function() {
                        const imageData = getImageData.apply(this, arguments);
                        // 미세한 노이즈 추가 (감지 어렵게)
                        for (let i = 0; i < imageData.data.length; i += 4) {
                            const noise = Math.floor(Math.random() * 3) - 1; // -1, 0, 1
                            imageData.data[i] = Math.max(0, Math.min(255, imageData.data[i] + noise));
                            imageData.data[i + 1] = Math.max(0, Math.min(255, imageData.data[i + 1] + noise));
                            imageData.data[i + 2] = Math.max(0, Math.min(255, imageData.data[i + 2] + noise));
                        }
                        return imageData;
                    };
                    
                    // AudioContext 핑거프린팅 우회
                    const AudioContext = window.AudioContext || window.webkitAudioContext;
                    if (AudioContext) {
                        const originalCreateOscillator = AudioContext.prototype.createOscillator;
                        AudioContext.prototype.createOscillator = function() {
                            const oscillator = originalCreateOscillator.apply(this, arguments);
                            const originalStart = oscillator.start;
                            oscillator.start = function() {
                                // 미세한 지연 추가
                                setTimeout(() => {
                                    originalStart.apply(this, arguments);
                                }, Math.random() * 2);
                            };
                            return oscillator;
                        };
                    }
                    
                    // Battery API 오버라이드
                    if (navigator.getBattery) {
                        navigator.getBattery = () => Promise.resolve({
                            charging: true,
                            chargingTime: 0,
                            dischargingTime: Infinity,
                            level: 0.8 + Math.random() * 0.2
                        });
                    }
                    
                    // Connection API 오버라이드
                    if (navigator.connection) {
                        Object.defineProperty(navigator, 'connection', {
                            get: () => ({
                                effectiveType: '4g',
                                rtt: 50 + Math.floor(Math.random() * 100),
                                downlink: 10 + Math.random() * 5,
                                saveData: false
                            })
                        });
                    }
                    
                    // Timezone 오버라이드 (한국 시간)
                    Date.prototype.getTimezoneOffset = function() {
                        return -540; // UTC+9 (한국)
                    };
                    
                    // Console.debug 오버라이드 (일부 사이트가 console을 체크함)
                    const originalDebug = console.debug;
                    console.debug = function() {
                        // 아무것도 하지 않음 (봇 감지 스크립트가 console을 체크하는 경우 대비)
                    };
                '''
            })
            
            logger.info("✓ 스텔스 스크립트 주입 완료 (페이지 로드 전)")
            
        except Exception as e:
            logger.warning(f"스텔스 스크립트 주입 실패: {e}")
    
    def randomize_fingerprint(self):
        """
        Canvas, WebGL 등의 핑거프린트를 랜덤화
        """
        try:
            # Canvas 핑거프린트 랜덤화
            canvas_script = """
            (function() {
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                ctx.textBaseline = 'top';
                ctx.font = '14px Arial';
                ctx.textBaseline = 'alphabetic';
                ctx.fillStyle = '#f60';
                ctx.fillRect(125, 1, 62, 20);
                ctx.fillStyle = '#069';
                ctx.fillText('Stealth Mode', 2, 15);
                ctx.fillStyle = 'rgba(102, 204, 0, 0.7)';
                ctx.fillText('Stealth Mode', 4, 17);
                return canvas.toDataURL();
            })();
            """
            self.driver.execute_script(canvas_script)
            
            # WebGL 핑거프린트 랜덤화
            webgl_script = """
            (function() {
                const canvas = document.createElement('canvas');
                const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
                if (gl) {
                    const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
                    if (debugInfo) {
                        const vendor = gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL);
                        const renderer = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL);
                        return {vendor: vendor, renderer: renderer};
                    }
                }
                return null;
            })();
            """
            self.driver.execute_script(webgl_script)
            
            logger.debug("✓ 핑거프린트 랜덤화 완료")
            
        except Exception as e:
            logger.warning(f"핑거프린트 랜덤화 실패: {e}")
    
    def human_like_delay(self, min_seconds: float = 0.5, max_seconds: float = 2.0):
        """
        사람처럼 랜덤 딜레이
        
        Args:
            min_seconds: 최소 대기 시간 (초)
            max_seconds: 최대 대기 시간 (초)
        """
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)
        return delay
    
    def human_like_mouse_movement(self, element=None, duration: float = None):
        """
        사람처럼 마우스 움직임 시뮬레이션
        
        Args:
            element: 이동할 요소 (선택사항)
            duration: 이동 시간 (초, None이면 랜덤)
        """
        try:
            actions = ActionChains(self.driver)
            
            if duration is None:
                duration = random.uniform(0.3, 0.8)
            
            if element:
                # 요소로 부드럽게 이동
                actions.move_to_element(element)
                # 약간의 랜덤 오프셋 추가
                x_offset = random.randint(-10, 10)
                y_offset = random.randint(-10, 10)
                actions.move_by_offset(x_offset, y_offset)
            else:
                # 랜덤 위치로 이동
                x = random.randint(100, 800)
                y = random.randint(100, 600)
                actions.move_by_offset(x, y)
            
            actions.perform()
            time.sleep(random.uniform(0.1, 0.3))
            
            logger.debug(f"✓ 마우스 움직임 시뮬레이션 완료 (duration: {duration:.2f}s)")
            
        except Exception as e:
            logger.debug(f"마우스 움직임 시뮬레이션 실패: {e}")
    
    def human_like_scroll(self, direction: str = 'down', amount: int = None):
        """
        사람처럼 스크롤
        
        Args:
            direction: 'up' 또는 'down'
            amount: 스크롤 양 (픽셀, None이면 랜덤)
        """
        try:
            if amount is None:
                amount = random.randint(200, 800)
            
            if direction == 'down':
                scroll_amount = amount
            else:
                scroll_amount = -amount
            
            # 부드러운 스크롤
            self.driver.execute_script(f"window.scrollBy({{top: {scroll_amount}, behavior: 'smooth'}});")
            
            # 스크롤 후 랜덤 대기
            self.human_like_delay(0.5, 1.5)
            
            logger.debug(f"✓ 스크롤 완료 ({direction}, {abs(scroll_amount)}px)")
            
        except Exception as e:
            logger.warning(f"스크롤 실패: {e}")
    
    def human_like_typing(self, element, text: str, typing_speed: float = None):
        """
        사람처럼 타이핑 (랜덤 속도)
        
        Args:
            element: 입력할 요소
            text: 입력할 텍스트
            typing_speed: 타이핑 속도 (초/문자, None이면 랜덤)
        """
        try:
            if typing_speed is None:
                typing_speed = random.uniform(0.05, 0.15)
            
            element.clear()
            
            for char in text:
                element.send_keys(char)
                # 랜덤 딜레이 (가끔 더 긴 딜레이)
                if random.random() < 0.1:  # 10% 확률로 긴 딜레이
                    time.sleep(random.uniform(0.3, 0.8))
                else:
                    time.sleep(typing_speed + random.uniform(-0.02, 0.02))
            
            logger.debug(f"✓ 타이핑 완료 ({len(text)} 문자)")
            
        except Exception as e:
            logger.warning(f"타이핑 실패: {e}")
    
    def apply_cdp_stealth(self):
        """
        CDP를 사용한 추가 스텔스 설정
        """
        try:
            # Network 조건 설정 (사람처럼 보이게)
            self.driver.execute_cdp_cmd('Network.emulateNetworkConditions', {
                'offline': False,
                'downloadThroughput': 10 * 1024 * 1024,  # 10 Mbps
                'uploadThroughput': 5 * 1024 * 1024,     # 5 Mbps
                'latency': random.randint(20, 100)        # 20-100ms 랜덤 지연
            })
            
            # CPU 스로틀링 (사람처럼 보이게)
            self.driver.execute_cdp_cmd('Emulation.setCPUThrottlingRate', {
                'rate': 1.0  # 정상 속도
            })
            
            # 시간대 설정 (한국)
            self.driver.execute_cdp_cmd('Emulation.setTimezoneOverride', {
                'timezoneId': 'Asia/Seoul'
            })
            
            # 언어 설정
            self.driver.execute_cdp_cmd('Emulation.setLocaleOverride', {
                'locale': 'ko-KR'
            })
            
            # Geolocation 오버라이드 (서울)
            self.driver.execute_cdp_cmd('Emulation.setGeolocationOverride', {
                'latitude': 37.5665 + random.uniform(-0.1, 0.1),
                'longitude': 126.9780 + random.uniform(-0.1, 0.1),
                'accuracy': 100
            })
            
            logger.info("✓ CDP 스텔스 설정 완료")
            
        except Exception as e:
            logger.warning(f"CDP 스텔스 설정 실패: {e}")
    
    def setup_stealth(self):
        """
        모든 스텔스 모드 설정 적용
        """
        logger.info("스텔스 모드 설정 시작...")
        
        # 1. CDP 스크립트 주입 (페이지 로드 전)
        self.inject_stealth_scripts()
        
        # 2. CDP 추가 설정
        self.apply_cdp_stealth()
        
        # 3. 핑거프린트 랜덤화
        self.randomize_fingerprint()
        
        logger.info("✓ 스텔스 모드 설정 완료")


class ProxyRotator:
    """프록시 로테이션 및 IP 변경 관리"""
    
    def __init__(self, adb_manager=None):
        """
        Args:
            adb_manager: ADB Manager 인스턴스 (선택사항, 휴대폰 IP 변경용)
        """
        self.adb = adb_manager
        self.proxy_list = []
        self.current_proxy_index = 0
    
    def set_proxy_list(self, proxy_list: list):
        """
        프록시 리스트 설정
        
        Args:
            proxy_list: 프록시 IP 리스트
        """
        self.proxy_list = proxy_list
        logger.info(f"프록시 리스트 설정 완료: {len(proxy_list)}개")
    
    def get_next_proxy(self) -> Optional[str]:
        """
        다음 프록시 가져오기
        
        Returns:
            프록시 IP 또는 None
        """
        if not self.proxy_list:
            return None
        
        proxy = self.proxy_list[self.current_proxy_index]
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxy_list)
        return proxy
    
    def rotate_mobile_ip(self, disable_duration: int = 3):
        """
        휴대폰 IP 변경 (데이터 연결 토글)
        
        Args:
            disable_duration: 데이터 연결 비활성화 시간 (초)
        
        Returns:
            bool: 성공 여부
        """
        if not self.adb:
            logger.warning("ADB Manager가 설정되지 않았습니다.")
            return False
        
        try:
            from test6 import DataConnectionManager
            data_manager = DataConnectionManager(adb=self.adb)
            data_manager.toggle_data_connection(disable_duration=disable_duration)
            logger.info(f"✓ 휴대폰 IP 변경 완료 (데이터 연결 토글: {disable_duration}초)")
            time.sleep(5)  # 네트워크 재연결 대기
            return True
        except Exception as e:
            logger.error(f"휴대폰 IP 변경 실패: {e}")
            return False
    
    def restart_driver_with_new_ip(self, driver: webdriver.Chrome, 
                                   chrome_options: Options,
                                   use_mobile_ip: bool = True) -> webdriver.Chrome:
        """
        IP 변경 후 드라이버 재시작
        
        Args:
            driver: 현재 WebDriver 인스턴스
            chrome_options: Chrome Options
            use_mobile_ip: 휴대폰 IP 사용 여부
        
        Returns:
            새로운 WebDriver 인스턴스
        """
        try:
            # 기존 드라이버 종료
            if driver:
                try:
                    driver.quit()
                except:
                    pass
            
            # IP 변경
            if use_mobile_ip and self.adb:
                self.rotate_mobile_ip(disable_duration=3)
            elif self.proxy_list:
                # 프록시 로테이션
                proxy = self.get_next_proxy()
                if proxy:
                    chrome_options.add_argument(f'--proxy-server=http://{proxy}')
                    logger.info(f"프록시 변경: {proxy}")
            
            # 새 드라이버 생성
            from selenium.webdriver.chrome.service import Service
            from webdriver_manager.chrome import ChromeDriverManager
            import os
            
            try:
                manager_path = ChromeDriverManager().install()
                if os.path.isdir(manager_path):
                    search_dir = manager_path
                else:
                    search_dir = os.path.dirname(manager_path)
                
                driver_path = None
                for root, dirs, files in os.walk(search_dir):
                    for file in files:
                        if file == 'chromedriver':
                            file_path = os.path.join(root, file)
                            if os.path.isfile(file_path) and os.access(file_path, os.X_OK):
                                if 'THIRD_PARTY' not in file_path:
                                    driver_path = file_path
                                    break
                    if driver_path:
                        break
                
                if driver_path:
                    service = Service(driver_path)
                else:
                    service = Service()
            except:
                service = Service()
            
            new_driver = webdriver.Chrome(service=service, options=chrome_options)
            logger.info("✓ 드라이버 재시작 완료 (새 IP 적용)")
            
            return new_driver
            
        except Exception as e:
            logger.error(f"드라이버 재시작 실패: {e}")
            raise


def create_stealth_driver(chrome_options: Options, 
                          adb_manager=None,
                          use_remote_device: bool = False,
                          remote_debugging_port: int = 9222) -> webdriver.Chrome:
    """
    스텔스 모드가 적용된 WebDriver 생성
    
    Args:
        chrome_options: Chrome Options
        adb_manager: ADB Manager 인스턴스 (선택사항)
        use_remote_device: 원격 디바이스 사용 여부
        remote_debugging_port: 원격 디버깅 포트
    
    Returns:
        스텔스 모드가 적용된 WebDriver
    """

    
    # 스텔스 모드 옵션 적용
    stealth = StealthMode(None)  # 임시로 None 전달
    chrome_options = stealth.apply_stealth_options(chrome_options, use_remote_device=use_remote_device)
    
    # 원격 디바이스 설정
    if use_remote_device:
        chrome_options.add_experimental_option("debuggerAddress", f"127.0.0.1:{remote_debugging_port}")
        logger.info(f"원격 디바이스 연결: localhost:{remote_debugging_port}")
    
    # ChromeDriver 경로 설정
    try:
        manager_path = ChromeDriverManager().install()
        if os.path.isdir(manager_path):
            search_dir = manager_path
        else:
            search_dir = os.path.dirname(manager_path)
        
        driver_path = None
        for root, dirs, files in os.walk(search_dir):
            for file in files:
                if file == 'chromedriver':
                    file_path = os.path.join(root, file)
                    if os.path.isfile(file_path) and os.access(file_path, os.X_OK):
                        if 'THIRD_PARTY' not in file_path:
                            driver_path = file_path
                            break
            if driver_path:
                break
        
        if driver_path:
            service = Service(driver_path)
        else:
            service = Service()
    except:
        service = Service()
    
    # 드라이버 생성
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # 스텔스 모드 설정 적용
    stealth = StealthMode(driver)
    stealth.setup_stealth()
    
    logger.info("✓ 스텔스 모드 WebDriver 생성 완료")
    
    return driver