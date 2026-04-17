"""
Redis配置模块 - G模块基础配置
"""

import os
from dotenv import load_dotenv

load_dotenv()


class RedisConfig:
    """Redis连接配置"""
    
    URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    TTL = int(os.getenv('REDIS_TTL', 259200))  # 72小时
    
    @classmethod
    def get_connection_params(cls):
        """获取连接参数"""
        # 解析Redis URL
        url = cls.URL
        if url.startswith('redis://'):
            # 简单解析 Redis URL
            import re
            match = re.match(r'redis://([^:]+):(\d+)/?(\d*)', url)
            if match:
                host, port, db = match.groups()
                db = int(db) if db else 0
                return {
                    'host': host,
                    'port': int(port),
                    'db': db,
                    'decode_responses': True,
                    'socket_timeout': 5,
                    'socket_connect_timeout': 5
                }
        # 默认参数
        return {
            'host': 'localhost',
            'port': 6379,
            'db': 0,
            'decode_responses': True,
            'socket_timeout': 5,
            'socket_connect_timeout': 5
        }
