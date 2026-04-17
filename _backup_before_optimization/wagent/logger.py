#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
日志记录器模块

功能：
1. 思考过程日志记录
2. JSON格式存储
3. 完整日志导出
4. 按阶段过滤
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional


class ThinkingLogger:
    """
    思考过程日志记录器
    
    记录AI的思考过程，支持：
    - 按阶段分类（director/researcher/writer）
    - JSON格式持久化存储
    - 完整日志导出
    - 时间戳追踪
    
    Attributes:
        log_path: 日志文件路径
        logs: 内存中的日志列表
    """
    
    def __init__(self, log_path: str = "logs/wagent.log"):
        """
        初始化日志记录器
        
        Args:
            log_path: 日志文件路径
        """
        self.log_path = Path(log_path)
        self.logs: List[Dict] = []
        
        # 确保日志目录存在
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
    
    async def log(self, stage: str, action: str, content: str, 
                  metadata: Optional[Dict] = None):
        """
        记录日志条目
        
        Args:
            stage: 阶段标识 (director/researcher/writer)
            action: 动作描述
            content: 内容详情
            metadata: 附加元数据
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "stage": stage,
            "action": action,
            "content": content[:500],  # 截断过长内容
            "metadata": metadata or {}
        }
        
        self.logs.append(entry)
        
        # 异步写入文件
        try:
            with open(self.log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except Exception:
            pass  # 静默失败
    
    async def save_full(self):
        """保存完整日志到JSON文件"""
        full_path = self.log_path.with_suffix('.full.json')
        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                json.dump(self.logs, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def get_logs_by_stage(self, stage: str) -> List[Dict]:
        """按阶段过滤日志"""
        return [log for log in self.logs if log.get('stage') == stage]
    
    def clear(self):
        """清空内存中的日志"""
        self.logs.clear()
    
    @property
    def count(self) -> int:
        """获取日志条目数量"""
        return len(self.logs)