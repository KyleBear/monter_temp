import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # 프록시 설정
    PROXY_IPS = os.getenv('PROXY_IPS', '').split(',') if os.getenv('PROXY_IPS') else []
    PROXY_IPS = [ip.strip() for ip in PROXY_IPS if ip.strip()]  # 공백 제거
    
    # Redis 설정
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    REDIS_DB = int(os.getenv('REDIS_DB', 0))
    
    # 엑셀 파일 경로
    EXCEL_FILE_PATH = os.getenv('EXCEL_FILE_PATH', 'products.xlsx')
    
    # 네이버 URL
    NAVER_MOBILE_URL = 'https://m.naver.com'
    
    # 검색 키워드
    # MAIN_KEYWORD_LIST = '바나나'
    # BASE_SEARCH_KEYWORD_LIST = '로깅 바나나'
    # TEMP_SEARCH_KEYWORD_LIST = '바나나 고당도 바나나 정발 낱발'
    MAIN_KEYWORD_LIST = '감자'
    BASE_SEARCH_KEYWORD_LIST = '디콤마 감자'
    TEMP_SEARCH_KEYWORD_LIST = '국내산 햇감자 특 2kg 부터 포슬포슬 우리감자 국민간식 땅속의사과'
    # 반복 횟수
    REPEAT_COUNT = 1
    # 나중에 글자수에 따라 바꾸는걸 고려 
    # 대기 시간 설정
    IMPLICIT_WAIT = 10
    EXPLICIT_WAIT = 2  # 검색창 찾기 대기 시간 단축 (10초 -> 5초)
    ACTION_DELAY = 6
    SEARCH_WAIT = 3  # 검색 실행 후 대기 시간

    NV_MID = '85883663786' # 땅속의 사과
    NV_MID_2 = '88253727321' # 다콤마 감자
    
    # USB 연결된 휴대폰 Chrome 설정
    # USE_REMOTE_DEVICE = os.getenv('USE_REMOTE_DEVICE', 'False').lower() == 'true'  # True: 실제 휴대폰 사용, False: PC Chrome 사용
    USE_REMOTE_DEVICE = 'True'  # True: 실제 휴대폰 사용, False: PC Chrome 사용
    # USE_REMOTE_DEVICE = 'False'  # True: 실제 휴대폰 사용, False: PC Chrome 사용
    # REMOTE_DEBUGGING_PORT = int(os.getenv('REMOTE_DEBUGGING_PORT', 9222))  # Chrome 원격 디버깅 포트
    REMOTE_DEBUGGING_PORT = 9222
