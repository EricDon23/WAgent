#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
核心配置模块

包含：
1. FeatureFlags - 功能开关配置系统
2. AsyncConfig - 异步任务配置
3. ConstraintConfig - 约束配置
4. SystemState - 系统状态枚举
5. UserCommand - 用户命令枚举
"""

import os
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from typing import Dict, Any, List


class SystemState(Enum):
    """系统状态枚举"""
    IDLE = auto()
    INITIALIZING = auto()
    READY = auto()
    WAITING_INPUT = auto()
    DIRECTOR_GENERATING = auto()
    DIRECTOR_REVIEWING = auto()
    RESEARCHER_GENERATING = auto()
    WRITER_GENERATING = auto()
    WRITER_REVIEWING = auto()
    MODIFYING = auto()
    PACKAGING = auto()
    COMPLETED = auto()


class UserCommand(Enum):
    """用户命令枚举"""
    CONTINUE = "continue"
    MODIFY = "modify"
    REGENERATE = "regenerate"
    FINISH = "finish"
    QUIT = "quit"
    HELP = "help"
    STATUS = "status"
    CONTEXT = "context"       # v5.2: 上下文管理
    CONSTRAINTS = "constraints"  # v5.2: 约束查看
    AUDIT = "audit"           # v5.2: 审计日志


@dataclass
class FeatureFlags:
    """功能开关配置
    
    支持从环境变量加载，提供灵活的配置管理。
    
    使用示例:
        flags = FeatureFlags.from_env()
        flags.enable_realtime_refresh = False
        print(flags.to_dict())
    """
    
    # 实时刷新相关
    enable_realtime_refresh: bool = True
    refresh_interval: float = 3.0
    smooth_transition: bool = True
    clear_on_refresh: bool = True
    
    # 字符转换相关
    enable_text_normalization: bool = True
    case_insensitive_commands: bool = True
    auto_trim_whitespace: bool = True
    normalize_unicode: bool = True
    
    # 错误处理相关
    graceful_degradation: bool = True
    auto_retry_on_error: bool = True
    max_retry_attempts: int = 3
    
    @classmethod
    def from_env(cls) -> 'FeatureFlags':
        """从环境变量加载配置"""
        def get_bool(key: str, default: bool) -> bool:
            val = os.getenv(key, str(default)).lower()
            return val in ('true', 'yes', '1', 'on')
        
        return cls(
            enable_realtime_refresh=get_bool('WAGENT_REFRESH', True),
            refresh_interval=float(os.getenv('WAGENT_REFRESH_INTERVAL', '3')),
            smooth_transition=get_bool('WAGENT_SMOOTH', True),
            clear_on_refresh=get_bool('WAGENT_CLEAR', True),
            enable_text_normalization=get_bool('WAGENT_NORMALIZE', True),
            case_insensitive_commands=get_bool('WAGENT_CASE_INSENSITIVE', True),
            auto_trim_whitespace=get_bool('WAGENT_TRIM', True),
            normalize_unicode=get_bool('WAGENT_UNICODE', True),
            graceful_degradation=True,
            auto_retry_on_error=True,
            max_retry_attempts=3
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    def validate(self) -> tuple[bool, List[str]]:
        """
        验证配置有效性
        
        Returns:
            (是否有效, 错误信息列表)
        """
        errors = []
        
        if self.refresh_interval < 0.5 or self.refresh_interval > 60:
            errors.append(f"刷新间隔应在0.5-60秒之间，当前值: {self.refresh_interval}")
        
        if self.max_retry_attempts < 1 or self.max_retry_attempts > 10:
            errors.append(f"重试次数应在1-10次之间，当前值: {self.max_retry_attempts}")
        
        return len(errors) == 0, errors


@dataclass
class AsyncConfig:
    """异步任务配置"""
    director_max_tokens: int = 2048
    director_temperature: float = 0.0
    writer_max_tokens: int = 4096
    writer_temperature: float = 1.0
    researcher_max_tokens: int = 3000
    researcher_temperature: float = 0.0
    cache_ttl: int = 3600
    stream_timeout: int = 180


@dataclass
class ConstraintConfig:
    """约束配置"""
    min_words: int = 1500
    max_words: int = 2500
    tolerance: float = 0.10
    
    def validate(self, actual_count: int) -> tuple[bool, str]:
        """
        校验字数是否符合约束
        
        Args:
            actual_count: 实际字数
            
        Returns:
            (是否通过, 描述信息)
        """
        min_allowed = self.min_words * (1 - self.tolerance)
        max_allowed = self.max_words * (1 + self.tolerance)
        
        if actual_count < min_allowed:
            return False, f"字数不足: {actual_count}字 (要求≥{self.min_words}字)"
        elif actual_count > max_allowed:
            return False, f"字数超标: {actual_count}字 (要求≤{self.max_words}字)"
        else:
            return True, f"✅ 字数符合: {actual_count}字 ({self.min_words}-{self.max_words})"
