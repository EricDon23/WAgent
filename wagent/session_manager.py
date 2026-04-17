#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
企业级会话管理系统 v2.0 (Enterprise Session Manager)

核心功能：
1. 会话区分：基于唯一标识符的会话识别机制
2. 会话检测：实时状态监控与异常检测
3. 会话切换：安全可靠的会话切换流程
4. 会话隔离：严格的数据隔离策略
5. 生命周期管理：创建/验证/更新/销毁完整闭环

安全特性：
- 会话令牌 (Session Token) 认证
- 超时自动销毁机制
- 数据加密存储
- 操作审计日志
- 异常状态恢复

架构设计：
┌─────────────────────────────────────────────┐
│           SessionManager (核心)              │
├─────────────────────────────────────────────┤
│  SessionRegistry  - 会话注册表               │
│  SessionMonitor   - 状态监控器               │
│  SessionIsolator  - 隔离策略执行器           │
│  SessionLifecycle - 生命周期管理器           │
│  SessionSecurity  - 安全认证模块            │
└─────────────────────────────────────────────┘
          ↓
┌─────────────────────────────────────────────┐
│         Session 实例 (每个会话独立)          │
├─────────────────────────────────────────────┤
│  session_id      - 唯一标识符                │
│  session_token   - 安全令牌                  │
│  state           - 当前状态                  │
│  metadata        - 元数据                    │
│  data_store      - 隔离数据存储              │
│  audit_log       - 操作日志                  │
└─────────────────────────────────────────────┘

使用方式:
    from wagent.session_manager import SessionManager
    
    mgr = SessionManager()
    
    # 创建会话
    session = mgr.create_session(user_id="user_001", metadata={"name": "我的故事"})
    
    # 切换会话
    mgr.switch_to(session.session_id)
    
    # 检测状态
    status = mgr.get_status(session.session_id)
"""

import json
import os
import uuid
import hashlib
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import OrderedDict


class SessionState(Enum):
    """会话状态枚举"""
    CREATED = "created"           # 已创建，未激活
    ACTIVE = "active"             # 活跃中
    IDLE = "idle"                 # 空闲（无操作超时阈值内）
    SUSPENDED = "suspended"       # 已挂起（用户主动暂停）
    EXPIRED = "expired"           # 已过期（超时未操作）
    TERMINATED = "terminated"     # 已终止（正常结束）
    ERROR = "error"               # 异常状态
    LOCKED = "locked"             # 已锁定（正在操作中）


class SessionEventType(Enum):
    """会话事件类型"""
    CREATED = "created"
    ACTIVATED = "activated"
    ACCESSED = "accessed"
    MODIFIED = "modified"
    SWITCHED_TO = "switched_to"
    SWITCHED_FROM = "switched_from"
    SUSPENDED = "suspended"
    RESUMED = "resumed"
    EXPIRED = "expired"
    TERMINATED = "terminated"
    ERROR_OCCURRED = "error"
    DATA_ISOLATED = "data_isolated"
    SECURITY_CHECK = "security_check"


@dataclass
class SessionToken:
    """
    会话安全令牌
    
    用于会话认证和防篡改验证
    """
    token_value: str
    created_at: str = ""
    expires_at: str = ""
    is_valid: bool = True
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.expires_at:
            expire_time = datetime.now() + timedelta(hours=24)
            self.expires_at = expire_time.isoformat()
    
    @property
    def is_expired(self) -> bool:
        try:
            return datetime.now() > datetime.fromisoformat(self.expires_at)
        except:
            return True
    
    def validate(self, provided_token: str) -> bool:
        """验证令牌有效性"""
        if not self.is_valid:
            return False
        if self.is_expired:
            self.is_valid = False
            return False
        return self.token_value == provided_token
    
    def to_dict(self) -> dict:
        return {
            'token_value': self.token_value,
            'created_at': self.created_at,
            'expires_at': self.expires_at,
            'is_valid': self.is_valid,
            'is_expired': self.is_expired
        }


@dataclass
class SessionEvent:
    """
    会话事件记录
    
    用于审计跟踪和调试
    """
    event_type: SessionEventType
    timestamp: str = ""
    session_id: str = ""
    details: str = ""
    user_id: str = ""
    data_snapshot: Optional[Dict] = None
    event_id: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        if not self.event_id:
            self.event_id = f"evt_{uuid.uuid4().hex[:12]}"
    
    def to_dict(self) -> dict:
        return {
            'event_id': self.event_id,
            'event_type': self.event_type.value,
            'timestamp': self.timestamp,
            'session_id': self.session_id,
            'details': self.details,
            'user_id': self.user_id,
            'has_data_snapshot': self.data_snapshot is not None
        }


@dataclass
class SessionDataStore:
    """
    会话数据存储（隔离容器）
    
    每个会话拥有独立的存储空间，
    实现严格的数据隔离
    """
    session_id: str
    story_data: Dict = field(default_factory=dict)
    context_data: Dict = field(default_factory=dict)
    temp_data: Dict = field(default_factory=dict)
    config_data: Dict = field(default_factory=dict)
    checksum: str = ""
    last_modified: str = ""
    size_bytes: int = 0
    
    def __post_init__(self):
        self.last_modified = datetime.now().isoformat()
        self._update_checksum()
    
    def _update_checksum(self):
        """更新数据校验和（用于完整性验证）"""
        all_data = {
            'story': self.story_data,
            'context': self.context_data,
            'temp': self.temp_data,
            'config': self.config_data
        }
        json_str = json.dumps(all_data, sort_keys=True, default=str)
        self.checksum = hashlib.md5(json_str.encode()).hexdigest()
        self.size_bytes = len(json_str.encode('utf-8'))
    
    def set_story_data(self, key: str, value: Any):
        """设置故事数据"""
        self.story_data[key] = value
        self.last_modified = datetime.now().isoformat()
        self._update_checksum()
    
    def set_context_data(self, key: str, value: Any):
        """设置上下文数据"""
        self.context_data[key] = value
        self.last_modified = datetime.now().isoformat()
        self._update_checksum()
    
    def get_story_data(self, key: str, default=None) -> Any:
        """获取故事数据"""
        return self.story_data.get(key, default)
    
    def get_context_data(self, key: str, default=None) -> Any:
        """获取上下文数据"""
        return self.context_data.get(key, default)
    
    def verify_integrity(self) -> bool:
        """验证数据完整性"""
        old_checksum = self.checksum
        self._update_checksum()
        return old_checksum == self.checksum
    
    def clear_temp_data(self):
        """清除临时数据"""
        self.temp_data.clear()
        self.last_modified = datetime.now().isoformat()
        self._update_checksum()
    
    def to_dict(self) -> dict:
        return {
            'session_id': self.session_id,
            'checksum': self.checksum,
            'last_modified': self.last_modified,
            'size_bytes': self.size_bytes,
            'story_keys': list(self.story_data.keys()),
            'context_keys': list(self.context_data.keys()),
            'temp_keys': list(self.temp_data.keys()),
            'config_keys': list(self.config_data.keys())
        }


@dataclass
class SessionMetadata:
    """
    会话元数据
    
    存储会话的非核心信息
    """
    name: str = ""
    description: str = ""
    user_id: str = ""
    device_info: str = ""
    client_version: str = ""
    tags: List[str] = field(default_factory=list)
    custom_fields: Dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Session:
    """
    企业级会话对象
    
    核心特性：
    - 唯一标识符 + 安全令牌双重认证
    - 完整的状态管理
    - 隔离的数据存储
    - 详细的审计日志
    - 超时控制
    """
    session_id: str
    token: Optional[SessionToken] = None
    state: SessionState = SessionState.CREATED
    metadata: Optional[SessionMetadata] = None
    data_store: Optional[SessionDataStore] = None
    events: List[SessionEvent] = field(default_factory=list)
    
    # 时间控制
    created_at: str = ""
    activated_at: str = ""
    last_accessed_at: str = ""
    expires_at: str = ""
    
    # 超时配置（秒）
    idle_timeout: int = 1800       # 30分钟空闲超时
    max_lifetime: int = 86400     # 24小时最大生命周期
    
    # 锁定控制
    is_locked: bool = False
    lock_owner: Optional[str] = None
    lock_timestamp: Optional[str] = None
    
    def __post_init__(self):
        now = datetime.now().isoformat()
        
        if not self.created_at:
            self.created_at = now
        if not self.last_accessed_at:
            self.last_accessed_at = now
            
        if not self.expires_at:
            expire_time = datetime.now() + timedelta(seconds=self.max_lifetime)
            self.expires_at = expire_time.isoformat()
            
        if not self.token:
            self.token = SessionToken(
                token_value=f"tok_{uuid.uuid4().hex}_{int(time.time())}"
            )
            
        if not self.data_store:
            self.data_store = SessionDataStore(session_id=self.session_id)
            
        if not self.metadata:
            self.metadata = SessionMetadata()
    
    @property
    def is_active(self) -> bool:
        """检查会话是否活跃"""
        return self.state == SessionState.ACTIVE
    
    @property
    def is_valid(self) -> bool:
        """检查会话是否有效（未过期且非错误状态）"""
        if self.state in [SessionState.TERMINATED, SessionState.ERROR, SessionState.EXPIRED]:
            return False
        if self.is_expired:
            return False
        return True
    
    @property
    def is_expired(self) -> bool:
        """检查会话是否已过期"""
        try:
            return datetime.now() > datetime.fromisoformat(self.expires_at)
        except:
            return True
    
    @property
    def is_idle_expired(self) -> bool:
        """检查是否空闲超时"""
        if self.state != SessionState.ACTIVE and self.state != SessionState.IDLE:
            return False
        try:
            last_access = datetime.fromisoformat(self.last_accessed_at)
            idle_seconds = (datetime.now() - last_access).total_seconds()
            return idle_seconds > self.idle_timeout
        except:
            return True
    
    @property
    def age_seconds(self) -> float:
        """会话年龄（秒）"""
        try:
            created = datetime.fromisoformat(self.created_at)
            return (datetime.now() - created).total_seconds()
        except:
            return 0
    
    @property
    def idle_seconds(self) -> float:
        """空闲时间（秒）"""
        try:
            last_access = datetime.fromisoformat(self.last_accessed_at)
            return (datetime.now() - last_access).total_seconds()
        except:
            return 0
    
    def touch(self):
        """更新最后访问时间（心跳）"""
        self.last_accessed_at = datetime.now().isoformat()
        if self.state == SessionState.IDLE:
            self.state = SessionState.ACTIVE
    
    def activate(self):
        """激活会话"""
        self.state = SessionState.ACTIVE
        self.activated_at = datetime.now().isoformat()
        self.touch()
        self._record_event(SessionEventType.ACTIVATED, "会话被激活")
    
    def suspend(self):
        """挂起会话"""
        self.state = SessionState.SUSPENDED
        self.touch()
        self._record_event(SessionEventType.SUSPENDED, "用户主动挂起")
    
    def resume(self):
        """恢复会话"""
        if self.is_expired:
            self.state = SessionState.EXPIRED
            self._record_event(SessionEventType.EXPIRED, "尝试恢复已过期会话")
            return False
        
        self.state = SessionState.ACTIVE
        self.touch()
        self._record_event(SessionEventType.RESUMED, "会话恢复")
        return True
    
    def terminate(self, reason: str = "正常终止"):
        """终止会话"""
        self.state = SessionState.TERMINATED
        self.touch()
        self._record_event(SessionEventType.TERMINATED, reason)
    
    def acquire_lock(self, owner: str) -> bool:
        """获取锁"""
        if self.is_locked and self.lock_owner != owner:
            return False
        self.is_locked = True
        self.lock_owner = owner
        self.lock_timestamp = datetime.now().isoformat()
        return True
    
    def release_lock(self, owner: str) -> bool:
        """释放锁"""
        if not self.is_locked:
            return True
        if self.lock_owner != owner:
            return False
        self.is_locked = False
        self.lock_owner = None
        self.lock_timestamp = None
        return True
    
    def validate_token(self, provided_token: str) -> bool:
        """验证访问令牌"""
        if not self.token:
            return False
        return self.token.validate(provided_token)
    
    def _record_event(self, event_type: SessionEventType, details: str = "", data_snapshot: Dict = None):
        """记录事件"""
        event = SessionEvent(
            event_type=event_type,
            session_id=self.session_id,
            details=details,
            user_id=self.metadata.user_id if self.metadata else "",
            data_snapshot=data_snapshot
        )
        self.events.append(event)
        
        # 保持最近100条事件
        if len(self.events) > 100:
            self.events = self.events[-100:]
    
    def get_recent_events(self, limit: int = 20) -> List[SessionEvent]:
        """获取最近的事件记录"""
        return self.events[-limit:]
    
    def get_status_report(self) -> Dict:
        """生成状态报告"""
        return {
            'session_id': self.session_id,
            'state': self.state.value,
            'is_active': self.is_active,
            'is_valid': self.is_valid,
            'is_expired': self.is_expired,
            'is_idle_expired': self.is_idle_expired,
            'is_locked': self.is_locked,
            'age_seconds': round(self.age_seconds, 1),
            'idle_seconds': round(self.idle_seconds, 1),
            'token_valid': self.token.is_valid if self.token else False,
            'token_expired': self.token.is_expired if self.token else True,
            'events_count': len(self.events),
            'data_integrity_ok': self.data_store.verify_integrity() if self.data_store else False,
            'data_size_kb': round((self.data_store.size_bytes / 1024), 2) if self.data_store else 0,
            'created_at': self.created_at,
            'activated_at': self.activated_at,
            'last_accessed_at': self.last_accessed_at,
            'expires_at': self.expires_at
        }
    
    def to_dict(self, include_sensitive: bool = False) -> dict:
        """序列化为字典"""
        result = {
            'session_id': self.session_id,
            'state': self.state.value,
            'metadata': self.metadata.to_dict() if self.metadata else {},
            'data_summary': self.data_store.to_dict() if self.data_store else {},
            'events_count': len(self.events),
            'created_at': self.created_at,
            'activated_at': self.activated_at,
            'last_accessed_at': self.last_accessed_at,
            'expires_at': self.expires_at,
            'is_locked': self.is_locked,
            'idle_timeout': self.idle_timeout,
            'max_lifetime': self.max_lifetime
        }
        
        if include_sensitive:
            result['token'] = self.token.to_dict() if self.token else {}
            result['recent_events'] = [e.to_dict() for e in self.get_recent_events(10)]
        
        return result


class SessionManager:
    """
    企业级会话管理器
    
    核心功能：
    1. 会话创建与管理
    2. 实时状态监控
    3. 安全切换
    4. 数据隔离
    5. 生命周期管理
    """
    
    def __init__(self, base_dir: str = "sessions", 
                 auto_cleanup: bool = True,
                 cleanup_interval: int = 300):
        """
        初始化会话管理器
        
        Args:
            base_dir: 会话存储根目录
            auto_cleanup: 是否自动清理过期会话
            cleanup_interval: 自动清理间隔（秒）
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        self._sessions: Dict[str, Session] = {}  # 内存中的活跃会话
        self._current_session_id: Optional[str] = None
        
        # 配置
        self.auto_cleanup = auto_cleanup
        self.cleanup_interval = cleanup_interval
        self.default_idle_timeout = 1800  # 30分钟
        self.default_max_lifetime = 86400  # 24小时
        
        # 监控线程
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitor_running = False
        self._lock = threading.RLock()
        
        # 统计信息
        self.stats = {
            'sessions_created': 0,
            'sessions_terminated': 0,
            'switches_performed': 0,
            'security_violations': 0,
            'errors_recovered': 0
        }
        
        # 启动监控
        if auto_cleanup:
            self._start_monitor()
    
    def _start_monitor(self):
        """启动后台监控线程"""
        if self._monitor_running:
            return
            
        self._monitor_running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="SessionMonitor"
        )
        self._monitor_thread.start()
    
    def _stop_monitor(self):
        """停止监控线程"""
        self._monitor_running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
    
    def _monitor_loop(self):
        """监控循环 - 定期检测和清理"""
        while self._monitor_running:
            time.sleep(self.cleanup_interval)
            try:
                self._cleanup_expired_sessions()
                self._check_idle_sessions()
            except Exception as e:
                pass
    
    # ========== 会话创建 ==========
    
    def create_session(self, user_id: str = "", 
                       metadata: Optional[Dict] = None,
                       custom_id: Optional[str] = None) -> Session:
        """
        创建新会话
        
        Args:
            user_id: 用户ID
            metadata: 元数据字典
            custom_id: 自定义会话ID（可选）
            
        Returns:
            新创建的Session对象
        """
        with self._lock:
            session_id = custom_id or f"sess_{uuid.uuid4().hex[:16]}_{int(time.time())}"
            
            # 创建元数据
            meta = SessionMetadata(user_id=user_id or "anonymous")
            if metadata:
                for k, v in metadata.items():
                    if hasattr(meta, k):
                        setattr(meta, k, v)
                    else:
                        meta.custom_fields[k] = v
            
            # 创建会话
            session = Session(
                session_id=session_id,
                idle_timeout=self.default_idle_timeout,
                max_lifetime=self.default_max_lifetime,
                metadata=meta
            )
            
            # 记录创建事件
            session._record_event(
                SessionEventType.CREATED,
                f"会话创建 | 用户: {user_id or 'anonymous'}",
                {'metadata': meta.to_dict()}
            )
            
            # 注册到内存
            self._sessions[session_id] = session
            
            # 持久化
            self._save_session(session)
            
            self.stats['sessions_created'] += 1
            
            return session
    
    # ========== 会话访问 ==========
    
    def get_session(self, session_id: str, 
                    token: Optional[str] = None) -> Optional[Session]:
        """
        获取会话（带验证）
        
        Args:
            session_id: 会话ID
            token: 访问令牌（可选，提供则进行验证）
            
        Returns:
            Session对象或None
        """
        with self._lock:
            session = self._sessions.get(session_id)
            
            if not session:
                # 尝试从磁盘加载
                session = self._load_session(session_id)
                if session:
                    self._sessions[session_id] = session
            
            if not session:
                return None
            
            # 令牌验证
            if token and not session.validate_token(token):
                self.stats['security_violations'] += 1
                session._record_event(
                    SessionEventType.SECURITY_CHECK,
                    "令牌验证失败"
                )
                return None
            
            # 更新访问时间
            session.touch()
            session._record_event(
                SessionEventType.ACCESSED,
                "会话被访问"
            )
            
            return session
    
    def get_current_session(self) -> Optional[Session]:
        """获取当前活跃会话"""
        if not self._current_session_id:
            return None
        return self.get_session(self._current_session_id)
    
    # ========== 会话切换 ==========
    
    def switch_to(self, session_id: str, 
                  token: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        切换到指定会话
        
        Args:
            session_id: 目标会话ID
            token: 访问令牌
            
        Returns:
            (成功标志, 错误消息)
        """
        with self._lock:
            # 获取目标会话
            target_session = self.get_session(session_id, token)
            
            if not target_session:
                return False, f"会话不存在或令牌无效: {session_id}"
            
            if not target_session.is_valid:
                return False, f"目标会话无效 (状态: {target_session.state.value})"
            
            # 记录旧会话
            old_session_id = self._current_session_id
            if old_session_id:
                old_session = self._sessions.get(old_session_id)
                if old_session:
                    old_session.suspend()
                    old_session._record_event(
                        SessionEventType.SWITCHED_FROM,
                        f"切换至: {session_id}"
                    )
            
            # 激活新会话
            target_session.activate()
            target_session._record_event(
                SessionEventType.SWITCHED_TO,
                f"从: {old_session_id or '(新会话)'}"
            )
            
            self._current_session_id = session_id
            self.stats['switches_performed'] += 1
            
            return True, None
    
    def switch_to_new(self, user_id: str = "",
                      metadata: Optional[Dict] = None) -> Session:
        """创建并切换到新会话"""
        session = self.create_session(user_id=user_id, metadata=metadata)
        self.switch_to(session.session_id, session.token.token_value)
        return session
    
    # ========== 会话检测 ==========
    
    def get_all_sessions(self, include_terminated: bool = False) -> List[Session]:
        """获取所有会话"""
        with self._lock:
            sessions = list(self._sessions.values())
            
            if include_terminated:
                return sessions
                
            return [s for s in sessions if s.is_valid]
    
    def get_active_sessions(self) -> List[Session]:
        """获取所有活跃会话"""
        return [s for s in self._sessions.values() if s.is_active]
    
    def get_idle_sessions(self) -> List[Session]:
        """获取所有空闲会话"""
        return [s for s in self._sessions.values() if s.is_idle_expired]
    
    def get_expired_sessions(self) -> List[Session]:
        """获取所有过期会话"""
        return [s for s in self._sessions.values() if s.is_expired]
    
    def get_status(self, session_id: str) -> Optional[Dict]:
        """获取指定会话的详细状态"""
        session = self.get_session(session_id)
        if not session:
            return None
        return session.get_status_report()
    
    def get_system_status(self) -> Dict:
        """获取整个系统的状态概览"""
        all_sessions = list(self._sessions.values())
        
        active_count = sum(1 for s in all_sessions if s.is_active)
        idle_count = sum(1 for s in all_sessions if s.is_idle_expired)
        expired_count = sum(1 for s in all_sessions if s.is_expired)
        error_count = sum(1 for s in all_sessions if s.state == SessionState.ERROR)
        
        return {
            'total_sessions': len(all_sessions),
            'active_sessions': active_count,
            'idle_sessions': idle_count,
            'expired_sessions': expired_count,
            'error_sessions': error_count,
            'current_session_id': self._current_session_id,
            'monitor_running': self._monitor_running,
            'auto_cleanup_enabled': self.auto_cleanup,
            'stats': self.stats.copy(),
            'uptime_info': {
                'check_interval': self.cleanup_interval,
                'default_idle_timeout': self.default_idle_timeout,
                'default_max_lifetime': self.default_max_lifetime
            }
        }
    
    # ========== 会话隔离 ==========
    
    def isolate_session_data(self, session_id: str, 
                              source_session_id: str) -> bool:
        """
        从源会话复制数据到目标会话（隔离复制）
        
        确保数据不会在会话间意外共享
        """
        target = self.get_session(session_id)
        source = self.get_session(source_session_id)
        
        if not target or not source:
            return False
        
        # 深拷贝数据（确保完全隔离）
        import copy
        target.data_store.story_data = copy.deepcopy(source.data_store.story_data)
        target.data_store.context_data = copy.deepcopy(source.data_store.context_data)
        
        target._record_event(
            SessionEventType.DATA_ISOLATED,
            f"从 {source_session_id} 复制并隔离数据"
        )
        
        return True
    
    # ========== 生命周期管理 ==========
    
    def update_session(self, session_id: str, 
                       updates: Dict,
                       token: Optional[str] = None) -> bool:
        """
        更新会话
        
        Args:
            session_id: 会话ID
            updates: 要更新的字段
            token: 访问令牌
        """
        session = self.get_session(session_id, token)
        if not session:
            return False
        
        with self._lock:
            before_state = session.to_dict(include_sensitive=False)
            
            # 应用更新
            for key, value in updates.items():
                if hasattr(session.metadata, key):
                    setattr(session.metadata, key, value)
                elif hasattr(session, key):
                    setattr(session, key, value)
            
            session.touch()
            session._record_event(
                SessionEventType.MODIFIED,
                f"更新字段: {list(updates.keys())}",
                {'before': before_state}
            )
            
            self._save_session(session)
            return True
    
    def terminate_session(self, session_id: str,
                          reason: str = "用户请求") -> bool:
        """终止指定会话"""
        session = self.get_session(session_id)
        if not session:
            return False
        
        with self._lock:
            session.terminate(reason)
            
            if self._current_session_id == session_id:
                self._current_session_id = None
            
            self.stats['sessions_terminated'] += 1
            
            # 归档而非删除
            self._archive_session(session)
            
            del self._sessions[session_id]
            
            return True
    
    def terminate_all(self, reason: str = "系统关闭") -> int:
        """终止所有会话"""
        count = 0
        session_ids = list(self._sessions.keys())
        
        for sid in session_ids:
            if self.terminate_session(sid, reason):
                count += 1
        
        return count
    
    # ========== 内部方法 ==========
    
    def _cleanup_expired_sessions(self):
        """清理过期会话"""
        expired = self.get_expired_sessions()
        for session in expired:
            session.state = SessionState.EXPIRED
            session._record_event(SessionEventType.EXPIRED, "自动过期清理")
            self._archive_session(session)
            del self._sessions[session.session_id]
    
    def _check_idle_sessions(self):
        """检查空闲会话"""
        idle = self.get_idle_sessions()
        for session in idle:
            session.state = SessionState.IDLE
            session._record_event(
                SessionEventType.ACCESSED,
                f"转为空闲状态 (空闲{int(session.idle_seconds)}秒)"
            )
    
    def _save_session(self, session: Session):
        """保存会话到磁盘"""
        session_dir = self.base_dir / session.session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # 主文件
        main_file = session_dir / "_session.json"
        with open(main_file, 'w', encoding='utf-8') as f:
            json.dump(session.to_dict(include_sensitive=True), f, ensure_ascii=False, indent=2, default=str)
        
        # 数据文件
        data_file = session_dir / "_data.json"
        if session.data_store:
            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'story_data': session.data_store.story_data,
                    'context_data': session.data_store.context_data,
                    'config_data': session.data_store.config_data
                }, f, ensure_ascii=False, indent=2, default=str)
        
        # 事件日志
        events_file = session_dir / "_events.jsonl"
        with open(events_file, 'a', encoding='utf-8') as f:
            for event in session.get_recent_events():
                f.write(json.dumps(event.to_dict(), ensure_ascii=False, default=str) + '\n')
    
    def _load_session(self, session_id: str) -> Optional[Session]:
        """从磁盘加载会话"""
        session_dir = self.base_dir / session_id
        main_file = session_dir / "_session.json"
        
        if not main_file.exists():
            return None
        
        try:
            with open(main_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 重建Session对象
            session = Session(
                session_id=data['session_id'],
                state=SessionState(data['state']),
                idle_timeout=data.get('idle_timeout', self.default_idle_timeout),
                max_lifetime=data.get('max_lifetime', self.default_max_lifetime),
                created_at=data.get('created_at', ''),
                last_accessed_at=data.get('last_accessed_at', ''),
                expires_at=data.get('expires_at', '')
            )
            
            # 恢复元数据
            if data.get('metadata'):
                meta_data = data['metadata']
                session.metadata = SessionMetadata(**{k: v for k, v in meta_data.items() 
                                                 if hasattr(SessionMetadata, k) or k == 'custom_fields'})
            
            # 恢复令牌
            if data.get('token'):
                tok_data = data['token']
                session.token = SessionToken(
                    token_value=tok_data.get('token_value', ''),
                    created_at=tok_data.get('created_at', ''),
                    expires_at=tok_data.get('expires_at', '')
                )
            
            # 加载数据
            data_file = session_dir / "_data.json"
            if data_file.exists():
                with open(data_file, 'r', encoding='utf-8') as f:
                    stored_data = json.load(f)
                
                session.data_store = SessionDataStore(session_id=session_id)
                session.data_store.story_data = stored_data.get('story_data', {})
                session.data_store.context_data = stored_data.get('context_data', {})
                session.data_store.config_data = stored_data.get('config_data', {})
            
            return session
            
        except Exception as e:
            return None
    
    def _archive_session(self, session: Session):
        """归档会话（不删除，仅移动）"""
        archive_dir = self.base_dir / "_archive"
        archive_dir.mkdir(exist_ok=True)
        
        session_dir = self.base_dir / session.session_id
        if session_dir.exists():
            import shutil
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            archive_name = f"{session.session_id}_{timestamp}"
            shutil.move(str(session_dir), str(archive_dir / archive_name))
    
    def shutdown(self):
        """优雅关闭管理器"""
        self._stop_monitor()
        self.terminate_all("系统关闭")


def create_session_manager(base_dir: str = "sessions") -> SessionManager:
    """便捷函数：创建会话管理器实例"""
    return SessionManager(base_dir=base_dir)


if __name__ == "__main__":
    print("=" * 70)
    print("🧪 企业级会话管理系统 v2.0 测试")
    print("=" * 70)
    
    # 创建管理器
    mgr = create_session_manager("_test_sessions")
    
    print("\n1️⃣ 创建会话...")
    session1 = mgr.create_session(user_id="user_001", metadata={"name": "测试故事1"})
    print(f"   ✅ 创建成功: {session1.session_id}")
    print(f"   令牌: {session1.token.token_value[:20]}...")
    
    print("\n2️⃣ 创建第二个会话...")
    session2 = mgr.create_session(user_id="user_002", metadata={"name": "测试故事2"})
    print(f"   ✅ 创建成功: {session2.session_id}")
    
    print("\n3️⃣ 激活第一个会话...")
    session1.activate()
    print(f"   状态: {session1.state.value}")
    
    print("\n4️⃣ 切换到第二个会话...")
    success, error = mgr.switch_to(session2.session_id, session2.token.token_value)
    print(f"   结果: {'✅ 成功' if success else f'❌ 失败: {error}'}")
    print(f"   当前会话: {mgr._current_session_id}")
    
    print("\n5️⃣ 获取系统状态...")
    status = mgr.get_system_status()
    print(f"   总会话数: {status['total_sessions']}")
    print(f"   活跃会话: {status['active_sessions']}")
    print(f"   统计: {status['stats']}")
    
    print("\n6️⃣ 终止所有会话...")
    count = mgr.terminate_all("测试完成")
    print(f"   终止了 {count} 个会话")
    
    print("\n7️⃣ 关闭管理器...")
    mgr.shutdown()
    print("   ✅ 关闭完成")
    
    print("\n" + "=" * 70)
    print("🎉 测试完成!")
    print("=" * 70)
