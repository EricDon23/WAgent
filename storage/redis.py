#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WAgent V3.1 Redis存储模块

基于错误修改.md要求实现：
- Redis高速缓存
- 本地文件优先策略
- 双重存储保障
"""

import json
import logging
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class RedisStorage:
    """
    Redis存储引擎 - V3.1数据层核心
    
    功能：
    - 高速缓存
    - 数据持久化
    - 与本地存储协同工作
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0", 
                 ttl: int = 259200):
        self.redis_url = redis_url
        self.ttl = ttl
        self._client = None
        self._available = False
        
        self._initialize()
    
    def _initialize(self):
        """初始化Redis连接"""
        try:
            import redis
            
            self._client = redis.Redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            
            # 测试连接
            self._client.ping()
            self._available = True
            logger.info(f"Redis连接成功: {self.redis_url}")
            
        except Exception as e:
            self._available = False
            logger.warning(f"Redis连接失败，将使用纯本地模式: {e}")
    
    @property
    def is_available(self) -> bool:
        """检查Redis是否可用"""
        return self._available
    
    def save(self, key: str, data: Any, category: str = "default") -> bool:
        """保存数据到Redis"""
        if not self._available:
            return False
        
        try:
            if isinstance(data, (dict, list)):
                value = json.dumps(data, ensure_ascii=False)
            else:
                value = str(data)
            
            full_key = f"{category}:{key}"
            self._client.setex(full_key, self.ttl, value)
            return True
            
        except Exception as e:
            logger.error(f"Redis保存失败 [{key}]: {e}")
            return False
    
    def load(self, key: str, category: str = "default") -> Optional[Any]:
        """从Redis加载数据"""
        if not self._available:
            return None
        
        try:
            full_key = f"{category}:{key}"
            value = self._client.get(full_key)
            
            if value:
                try:
                    return json.loads(value)
                except:
                    return value
            
            return None
            
        except Exception as e:
            logger.error(f"Redis读取失败 [{key}]: {e}")
            return None
    
    def delete(self, key: str = None, pattern: str = None) -> bool:
        """删除Redis数据"""
        if not self._available:
            return False
        
        try:
            if key:
                # 删除指定键的所有分类
                categories = ["meta", "setting", "content", "research", "system"]
                for cat in categories:
                    full_key = f"{cat}:{key}"
                    self._client.delete(full_key)
                    
            elif pattern:
                # 批量删除匹配的键
                keys = [k for k in self._client.keys(pattern)]
                if keys:
                    self._client.delete(*keys)
            
            return True
            
        except Exception as e:
            logger.error(f"Redis删除失败: {e}")
            return False
    
    def exists(self, key: str, category: str = "default") -> bool:
        """检查键是否存在"""
        if not self._available:
            return False
        
        try:
            full_key = f"{category}:{key}"
            return bool(self._client.exists(full_key))
        except:
            return False
    
    def get_all_keys(self, pattern: str = "*") -> list:
        """获取所有匹配的键"""
        if not self._available:
            return []
        
        try:
            return [k for k in self._client.keys(pattern)]
        except:
            return []
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        status = {
            "available": self._available,
            "url": self.redis_url
        }
        
        if self._available:
            try:
                info = self._client.info()
                status["connected_clients"] = info.get("connected_clients", 0)
                status["used_memory"] = info.get("used_memory_human", "N/A")
                status["uptime_seconds"] = info.get("uptime_in_seconds", 0)
            except:
                status["error"] = "无法获取详细信息"
        else:
            status["error"] = "Redis不可用"
        
        return status


def create_redis_storage(redis_url: str = "redis://localhost:6379/0",
                       ttl: int = 259200) -> RedisStorage:
    """工厂函数：创建Redis存储实例"""
    return RedisStorage(redis_url, ttl)
