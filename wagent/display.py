#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
实时状态显示系统模块

功能：
1. 平滑刷新机制（防闪烁双缓冲）
2. 智能内容更新检测
3. ANSI转义码支持
4. 进度条动画
5. 刷新统计信息
"""

import os
import sys
import time
import threading
from typing import Dict, Any, Optional

try:
    from rich.console import Console
    from rich.table import Table
    RICH_AVAILABLE = True
except ImportError:
    Console = None
    Table = None
    RICH_AVAILABLE = False

from .config import SystemState, FeatureFlags


class RealtimeDisplay:
    """
    增强型实时状态显示器
    
    v4.1/v4.2 新增特性：
    - 平滑过渡：使用ANSI转义码减少闪烁
    - 双缓冲机制：避免界面撕裂
    - 智能刷新：仅在内容变化时更新
    - 可配置性：支持启用/禁用
    - 统计信息：记录刷新次数和优化率
    
    Attributes:
        flags: 功能配置
        state: 当前系统状态
        stage: 当前阶段描述
        progress: 进度百分比 (0-100)
        message: 状态消息
        elapsed: 已运行时间(秒)
        details: 附加详细信息
    """
    
    def __init__(self, flags: FeatureFlags = None):
        """
        初始化显示器
        
        Args:
            flags: FeatureFlags配置对象
        """
        self.flags = flags or FeatureFlags()
        
        # 状态数据
        self.state = SystemState.IDLE
        self.stage = ""
        self.progress = 0.0
        self.message = ""
        self.elapsed = 0.0
        self.details: Dict[str, Any] = {}
        self.last_update = ""
        
        # 线程控制
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.start_time = time.time()
        
        # 双缓冲（防闪烁）
        self._buffer: str = ""
        self._last_rendered: str = ""
        
        # 统计信息
        self._refresh_count: int = 0
        self._skip_count: int = 0
        
        # 控制台实例
        self.console = Console() if RICH_AVAILABLE else None
    
    def start(self):
        """启动显示线程"""
        if not self.flags.enable_realtime_refresh:
            if self.console:
                self.console.print("[dim]ℹ️ 实时刷新已禁用[/dim]")
            return
        
        self._running = True
        self.start_time = time.time()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
    
    def stop(self):
        """停止显示线程"""
        self._running = False
        
        if self._thread:
            self._thread.join(timeout=2)
            
            # 显示最终统计
            if self.flags.enable_realtime_refresh and self._refresh_count > 0 and self.console:
                total = self._refresh_count + self._skip_count
                skip_rate = (self._skip_count / total * 100) if total > 0 else 0
                self.console.print(
                    f"[dim]📊 刷新统计: {self._refresh_count}次刷新, "
                    f"{self._skip_count}次跳过 ({skip_rate:.1f}%优化率)[/dim]"
                )
    
    def update(self, state: SystemState, stage: str = "", progress: float = 0.0,
               message: str = "", **kwargs):
        """更新状态"""
        with self._lock:
            self.state = state
            self.stage = stage
            self.progress = min(100, max(0, progress))
            self.message = message
            self.elapsed = time.time() - self.start_time
            self.details.update(kwargs)
            self.last_update = time.strftime("%H:%M:%S")
    
    def _loop(self):
        """主循环（带平滑过渡）"""
        while self._running:
            try:
                with self._lock:
                    current_content = self._format()
                
                # 智能刷新：仅在内容变化时更新
                if current_content != self._last_rendered:
                    self._render(current_content)
                    self._refresh_count += 1
                else:
                    self._skip_count += 1
                
                time.sleep(self.flags.refresh_interval)
                
            except Exception as e:
                if self.flags.graceful_degradation:
                    time.sleep(self.flags.refresh_interval)
                else:
                    raise
    
    def _render(self, content: str):
        """渲染内容到控制台"""
        try:
            if self.flags.smooth_transition and self._supports_ansi():
                self._smooth_render(content)
            elif self.flags.clear_on_refresh:
                os.system('cls' if os.name == 'nt' else 'clear')
                if self.console:
                    self.console.print(content)
                else:
                    print(content)
            else:
                if self.console:
                    self.console.print(content)
                else:
                    print(content)
            
            self._last_rendered = content
            
        except Exception:
            try:
                print(content) if not self.console else None
            except Exception:
                pass
    
    def _smooth_render(self, content: str):
        """平滑渲染（使用ANSI转义码）"""
        sys.stdout.write('\033[H')      # 光标移到顶部
        sys.stdout.write('\033[J')      # 清除屏幕
        sys.stdout.flush()
        
        if self.console:
            self.console.print(content)
        else:
            print(content)
    
    def _supports_ansi(self) -> bool:
        """检测终端是否支持ANSI转义码"""
        if os.name == 'nt':
            import platform
            version = platform.version()
            major_version = int(version.split('.')[0]) if version else 0
            return major_version >= 10
        
        term = os.environ.get('TERM', '')
        return term not in ('dumb', '') or hasattr(sys.stdout, 'isatty')
    
    def _format(self) -> str:
        """格式化状态显示内容"""
        s = self
        progress_bar = self._create_progress_bar(s.progress)
        
        lines = [
            "=" * 70,
            "⚡ WAgent v4.2 - 故事创作系统",
            "=" * 70,
            "",
            f"📊 状态: {s.state.name}",
            f"🎯 阶段: {s.stage or '就绪'}",
            "",
            f"⏱️ 已运行: {s.elapsed:.1f}s",
            f"📈 进度: {progress_bar} {s.progress:.0f}%",
            "",
            f"💬 {s.message}",
        ]
        
        if s.details:
            lines.append("")
            lines.append("📋 详情:")
            for k, v in s.details.items():
                val = str(v)[:50] + "..." if len(str(v)) > 50 else str(v)
                lines.append(f"   • {k}: {val}")
        
        lines.extend([
            "",
            f"🔄 刷新: #{self._refresh_count+1} | ⏰ {s.last_update}",
            "",
            "-" * 70,
            "按 Ctrl+C 安全退出"
        ])
        
        return "\n".join(lines)
    
    def _create_progress_bar(self, progress: float) -> str:
        """创建动态进度条"""
        width = 20
        filled = int(progress / 100 * width)
        empty = width - filled
        return f"[{'█' * filled}{'░' * empty}]"
    
    def force_refresh(self):
        """强制立即刷新"""
        with self._lock:
            content = self._format()
        if content != self._last_rendered:
            self._render(content)