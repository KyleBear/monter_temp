Table product {
  product_id bigint [primary key, note: 'AUTO_INCREMENT']
  main_keyword varchar
  base_search_keyword varchar
  temp_search_keyword varchar
  nv_mid varchar
  slot int [note: '제품당 시간당 허용 slot']
  hit int  [note: '현재 시간당 사용 hit']
  created_at timestamp
  updated_at timestamp
}

# 한번에 bulk 로 insert select 해야하는 테이블

Table proxy_status {
  proxy_id bigint [primary key, note: 'AUTO_INCREMENT']
  proxy_ip varchar
  proxy_port int
  latency_ms float [note: 'Ping/RTT 측정(ms)']
  success_rate float [note: '최근 요청 성공률 %']
  is_active boolean [note: '현재 사용 가능한지']
  last_checked timestamp
}

# 매일 6시 ip check list 로 돌아가는 테이블

Table proxy_log {
  log_id bigint [primary key, note: 'AUTO_INCREMENT']
  product_id bigint [not null]
  proxy_id bigint [not null]
  request_time timestamp
  request_url varchar
  status varchar [note: 'success / fail']
  response_code int
  response_time_ms float
}

Ref: product.product_id < proxy_log.product_id
Ref: proxy_status.proxy_id < proxy_log.proxy_id


Table cookie_collection {
  collection_id bigint [primary key, note: 'AUTO_INCREMENT']
  proxy_id bigint [not null]
  cookie_json json
  created_at timestamp
  updated_at timestamp
}

# 쿠키 수집 테이블 # 프록시 ip 포함 (프록시 id 로 join)
Ref: proxy_status.proxy_id < cookie_collection.proxy_id