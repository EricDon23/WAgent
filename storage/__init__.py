#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WAgent V3.1 存储管理器（统一数据层）

基于项目任务.md 2.9节实现：
- Redis高速缓存 + 本地文件持久化双重存储
- 统一数据读写接口
- 数据分类存储（元数据/设定/内容/研究/系统）
- 压缩优化 + 分层存储策略
"""

import os
import sys
import json
import gzip
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class StorageConfig:
    """存储配置"""
    base_dir: str = "stories"
    use_redis: bool = True
    compress_threshold: int = 1024  # 超过此字节数自动压缩
    ttl_seconds: int = 259200  # 72小时


class StorageManager:
    """
    统一存储管理器 - V3.1数据层核心
    
    提供统一的Redis+本地文件双重存储接口，
    对上层屏蔽存储细节。
    """
    
    DATA_CATEGORIES = {
        'meta': '元数据',
        'setting': '设定数据', 
        'content': '内容数据',
        'research': '研究数据',
        'system': '系统数据'
    }
    
    def __init__(self, config: StorageConfig = None):
        self.config = config or StorageConfig()
        self.base_dir = Path(self.config.base_dir)
        
        self._redis_available = False
        self._g_module = None
        
        self._init_storage()
    
    def _init_storage(self):
        """初始化存储后端"""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        if self.config.use_redis:
            try:
                from data.redis_config import RedisConfig
                rc = RedisConfig()
                health = rc.health_check()
                
                if health.get('status') == 'connected':
                    self._redis_available = True
                    from data.g_module import GModule
                    self._g_module = GModule(base_dir=str(self.base_dir))
                    logger.info(f"存储层初始化: Redis(✓) + 本地文件")
                else:
                    logger.info(f"存储层初始化: 纯本地模式 (Redis不可用)")
                    
            except Exception as e:
                logger.warning(f"Redis初始化失败: {e}，使用纯本地模式")
    
    def save(
        self,
        story_id: str,
        key: str,
        data: Any,
        category: str = 'content'
    ) -> bool:
        """
        保存数据（双写：本地+Redis）
        
        Args:
            story_id: 故事ID
            key: 数据键名
            data: 数据内容（支持dict/list/str）
            category: 数据类别
        """
        success = True
        
        try:
            serialized = self._serialize(data)
            
            local_path = self._get_local_path(story_id, key, category)
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(local_path, 'w', encoding='utf-8') as f:
                if isinstance(data, (dict, list)):
                    json.dump(data, f, indent=2, ensure_ascii=False)
                else:
                    f.write(str(data))
            
            if self._redis_available and self._g_module:
                redis_key = f"story:{story_id}:{key}"
                try:
                    self._g_module._set_to_redis(redis_key, data if isinstance(data, dict) else {"value": data})
                except Exception as e:
                    logger.warning(f"Redis写入失败 [{redis_key}]: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"保存失败 [{story_id}/{key}]: {e}")
            return False
    
    def load(
        self,
        story_id: str,
        key: str,
        category: str = 'content',
        default: Any = None
    ) -> Any:
        """
        加载数据（优先本地，回退Redis）
        """
        local_path = self._get_local_path(story_id, key, category)
        
        if local_path.exists():
            try:
                with open(local_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content.startswith('{') or content.startswith('['):
                        return json.loads(content)
                    return content
            except Exception as e:
                logger.warning(f"本地读取失败: {e}")
        
        if self._redis_available and self._g_module:
            redis_key = f"story:{story_id}:{key}"
            try:
                data = self._g_module._get_from_redis(redis_key)
                if data is not None:
                    if isinstance(data, dict) and 'value' in data and len(data) == 1:
                        return data['value']
                    return data
            except Exception as e:
                logger.warning(f"Redis读取失败: {e}")
        
        return default
    
    def delete(self, story_id: str, key: str = None) -> bool:
        """删除数据"""
        try:
            if key:
                for cat in self.DATA_CATEGORIES:
                    path = self._get_local_path(story_id, key, cat)
                    if path.exists():
                        path.unlink()
                
                if self._redis_available:
                    redis_key = f"story:{story_id}:{key}"
                    self._delete_redis_key(redis_key)
            else:
                story_dir = self.base_dir / story_id
                if story_dir.exists():
                    import shutil
                    shutil.rmtree(str(story_dir))
                
                if self._redis_available:
                    self._delete_redis_keys_pattern(f"story:{story_id}:*")
            
            return True
        except Exception as e:
            logger.error(f"删除失败: {e}")
            return False
    
    def exists(self, story_id: str, key: str = None) -> bool:
        """检查数据是否存在"""
        if key:
            for cat in self.DATA_CATEGORIES:
                path = self._get_local_path(story_id, key, cat)
                if path.exists():
                    return True
            return False
        else:
            return (self.base_dir / story_id).exists()
    
    def list_stories(self) -> List[Dict]:
        """列出所有故事"""
        stories = []
        
        if self.base_dir.exists():
            for sd in self.base_dir.iterdir():
                if sd.is_dir() and not sd.name.startswith('.'):
                    meta = self.load(sd.name, 'meta', 'meta')
                    stories.append({
                        'story_id': sd.name,
                        'title': meta.get('story_name', sd.name) if isinstance(meta, dict) else sd.name,
                        'updated': datetime.fromtimestamp(sd.stat().st_mtime).isoformat(),
                        'chapter_count': len(list(sd.glob('chapters/*.json'))) if (sd/'chapters').exists() else 0
                    })
        
        return sorted(stories, key=lambda x: x['updated'], reverse=True)
    
    def get_story_path(self, story_id: str) -> Path:
        """获取故事本地路径"""
        return self.base_dir / story_id
    
    def _get_local_path(self, story_id: str, key: str, category: str) -> Path:
        """获取本地文件路径"""
        cat_dirs = {
            'meta': '',
            'setting': '',
            'content': 'chapters',
            'research': 'research',
            'system': ''
        }
        
        sub = cat_dirs.get(category, '')
        
        if category == 'content' and key.startswith('chapter_'):
            return self.base_dir / story_id / sub / f"{key}.json"
        elif category == 'setting' and key == 'global_setting':
            return self.base_dir / story_id / "global_setting.json"
        elif category == 'meta':
            return self.base_dir / story_id / "meta.json"
        else:
            return self.base_dir / story_id / sub / f"{key}.json"
    
    def _serialize(self, data: Any) -> str:
        """序列化数据"""
        if isinstance(data, (dict, list)):
            return json.dumps(data, ensure_ascii=False)
        return str(data)
    
    def _delete_redis_key(self, key: str):
        """删除Redis键"""
        try:
            from data.redis_config import RedisConfig
            rc = RedisConfig()
            if rc._redis_client:
                rc._redis_client.delete(key)
        except:
            pass
    
    def _delete_redis_keys_pattern(self, pattern: str):
        """批量删除Redis键"""
        try:
            from data.redis_config import RedisConfig
            rc = RedisConfig()
            if rc._redis_client:
                keys = [k.decode() if isinstance(k, bytes) else k 
                       for k in rc._redis_client.keys(pattern)]
                if keys:
                    rc._redis_client.delete(*keys)
        except:
            pass


def create_storage_manager(**kwargs) -> StorageManager:
    """工厂函数"""
    return StorageManager(**kwargs)
