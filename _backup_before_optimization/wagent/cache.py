#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
缓存管理器模块

功能：
1. 内存缓存（默认）
2. Redis缓存（可选）
3. 双层缓存策略
4. TTL过期机制
"""

import json
from typing import Dict, Any, Optional

try:
    import aioredis
    REDIS_AVAILABLE = True
except ImportError:
    aioredis = None
    REDIS_AVAILABLE = False


class AsyncCacheManager:
    """
    异步缓存管理器
    
    支持双层缓存：
    - 第一层：内存缓存（快速访问）
    - 第二层：Redis缓存（持久化、跨进程共享）
    
    Attributes:
        cache: 内存缓存字典
        redis_client: Redis客户端实例（可选）
    """
    
    def __init__(self):
        self.cache: Dict[str, Dict] = {}
        self.redis_client = None
    
    async def init(self):
        """初始化Redis连接（如果可用）"""
        if REDIS_AVAILABLE:
            try:
                import os
                url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
                self.redis_client = await aioredis.from_url(url)
            except Exception:
                self.redis_client = None
    
    def key(self, prefix: str, *args) -> str:
        """生成缓存键"""
        return f"{prefix}:{':'.join(map(str, args))}"
    
    async def get(self, k: str) -> Optional[Dict]:
        """获取缓存值"""
        if self.redis_client:
            try:
                d = await self.redis_client.get(k)
                if d:
                    return json.loads(d)
            except Exception:
                pass
        
        return self.cache.get(k)
    
    async def set(self, k: str, v: Dict, ttl: int = 3600):
        """设置缓存值"""
        self.cache[k] = v
        
        if self.redis_client:
            try:
                await self.redis_client.setex(k, ttl, 
                    json.dumps(v, ensure_ascii=False))
            except Exception:
                pass
    
    async def close(self):
        """关闭连接"""
        if self.redis_client:
            await self.redis_client.close()
    
    def clear(self):
        """清空内存缓存"""
        self.cache.clear()
    
    @property
    def size(self) -> int:
        """获取内存缓存大小"""
        return len(self.cache)