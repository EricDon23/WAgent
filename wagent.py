#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WAgent v5.3 - 智能交互故事创作系统 (入口文件)

v5.3 核心升级：
1. 智能界面刷新机制（AI生成时刷新，用户输入时静止）
2. 增强会话管理（无缝切换+命令提示系统）
3. 交互控制功能（随时打断AI输出+平滑过渡）
4. 框架优化清理（模块化重构+移除废弃代码）

架构设计：
├── wagent/                    # 核心包
│   ├── config.py              # 配置与数据结构
│   ├── controller.py          # 主控制器 (v5.2)
│   ├── display.py             # 智能显示系统
│   ├── constraint_manager.py  # 约束保障系统
│   ├── story_session.py       # 会话持久化
│   ├── engines/               # AI引擎
│   └── utils/                 # 工具模块
└── wagent.py                  # 本文件（入口）

使用方法：
    python wagent.py              # 启动交互式创作
    python wagent.py --quick       # 快速验证环境
    python wagent.py --list        # 列出所有已保存的故事
    python wagent.py --resume ID   # 恢复指定会话

作者：WAgent Team
版本：v5.3 Smart Interactive
日期：2026-04-17
"""

import asyncio
import json
import os
import sys
import argparse
import signal
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

try:
    from rich.console import Console as RichConsole
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich.text import Text
    RICH_AVAILABLE = True
    console = RichConsole()
except ImportError:
    RichConsole = Panel = Markdown = Text = None
    RICH_AVAILABLE = False
    console = None


class InputPromptManager:
    """
    输入提示管理器 (v5.3+ 新增)
    
    核心功能：
    - 视觉清晰的输入提示（与常规输出区分）
    - 上下文特定的提示信息
    - 输入格式/内容指导
    - 防刷屏验证机制
    """
    
    def __init__(self, console=None):
        self.console = console or (RichConsole() if RICH_AVAILABLE else None)
        self._input_active = False
        self._last_prompt_context = ""
    
    def _format_prompt_header(self, context: str, instructions: str = None):
        """格式化提示头部信息"""
        if self.console and Text:
            header = Text.assemble(
                ("[INPUT] ", "bold yellow"),
                (context, "cyan"),
                style="white"
            )
            return header
        else:
            return f"[INPUT] {context}"
    
    def prompt(self, 
              context: str, 
              prompt_text: str, 
              instructions: str = None, 
              validation_func=None,
              default: str = None) -> str:
        """
        显示带上下文的输入提示并获取用户输入
        
        Args:
            context: 输入的上下文（如"会话选择"、"章节编号"等）
            prompt_text: 具体的提示问题
            instructions: 可选的格式/内容指导说明
            validation_func: 可选的验证函数，返回True表示有效
            default: 默认值（可选）
        
        Returns:
            用户输入值（保证不为空，除非default为None）
        
        防刷屏机制：
        - 在此方法执行期间，所有刷屏操作将被阻塞
        """
        self._input_active = True
        self._last_prompt_context = context
        
        try:
            # 显示上下文标题
            if self.console:
                from rich.panel import Panel
                self.console.print()
                panel = Panel(
                    self._format_prompt_header(context),
                    border_style="yellow",
                    padding=(0, 1)
                )
                self.console.print(panel)
            else:
                print(f"\n{'='*60}")
                print(f"[INPUT] {context}")
                print(f"{'='*60}")
            
            # 显示格式指导（如果有）
            if instructions:
                if self.console:
                    self.console.print(f"[dim]{instructions}[/dim]")
                else:
                    print(f"提示: {instructions}")
            
            # 显示提示并获取输入
            full_prompt = f"\n{prompt_text}"
            if default:
                full_prompt += f" [{default}]"
            full_prompt += ": "
            
            while True:
                if self.console:
                    from rich.prompt import Prompt as RichPrompt
                    user_input = RichPrompt.ask(full_prompt, default=default)
                else:
                    user_input = input(full_prompt)
                    
                # 应用验证
                if user_input is None and default is not None:
                    user_input = default
                    
                if validation_func:
                    if validation_func(user_input):
                        break
                    else:
                        if self.console:
                            self.console.print("[red]输入无效，请重试[/red]")
                        else:
                            print("输入无效，请重试")
                else:
                    break
            
            return user_input
            
        finally:
            self._input_active = False
    
    def confirm(self, 
               context: str, 
               question: str, 
               default: bool = False,
               danger: bool = False) -> bool:
        """
        显示确认提示（带上下文）
        
        Args:
            context: 上下文
            question: 确认问题
            default: 默认值
            danger: 是否是危险操作（红色提示）
        
        Returns:
            True/False
        """
        self._input_active = True
        try:
            if self.console:
                from rich.prompt import Confirm as RichConfirm
                from rich.panel import Panel
                
                border_style = "red" if danger else "yellow"
                if Text:
                    header = Text.assemble(
                        ("[CONFIRM] ", "bold " + ("red" if danger else "yellow")),
                        (context, "cyan"),
                        style="white"
                    )
                else:
                    header = f"[CONFIRM] {context}"
                
                self.console.print()
                panel = Panel(header, border_style=border_style, padding=(0, 1))
                self.console.print(panel)
                
                return RichConfirm.ask(question, default=default)
            else:
                print(f"\n[CONFIRM] {context}")
                print("-" * 40)
                while True:
                    resp = input(f"{question} (y/n) [{ 'y' if default else 'n'}]: ").lower().strip()
                    if resp in ['y', 'yes']:
                        return True
                    elif resp in ['n', 'no']:
                        return False
                    elif not resp:
                        return default
        finally:
            self._input_active = False
    
    def is_waiting_for_input(self) -> bool:
        """检查是否正在等待用户输入（防刷屏检查点）"""
        return self._input_active


class SmartDisplayController:
    """
    智能显示控制器 (v5.3+ 增强版)
    
    核心功能：
    - 状态感知：区分"AI生成中"和"等待用户输入"
    - 智能刷新：仅在AI生成时触发界面更新
    - 输入保护：用户输入时保持界面静止（严格防刷屏）
    - 打断支持：支持优雅中断当前操作
    """
    
    def __init__(self):
        self.console = RichConsole() if RICH_AVAILABLE else None
        self._state = "idle"  # idle/generating/waiting_input/interrupted
        self._refresh_enabled = True
        self._interrupt_requested = False
        self._lock = threading.Lock()
        self._input_prompt_mgr = InputPromptManager(self.console)
        
    def set_state(self, state: str):
        """设置当前状态"""
        with self._lock:
            self._state = state
            
    def is_generating(self) -> bool:
        """检查是否正在AI生成"""
        return self._state == "generating"
    
    def is_waiting_input(self) -> bool:
        """检查是否在等待用户输入"""
        return self._state == "waiting_input" or self._input_prompt_mgr.is_waiting_for_input()
    
    def request_interrupt(self):
        """请求中断当前操作"""
        with self._lock:
            self._interrupt_requested = True
            
    def check_interrupt(self) -> bool:
        """检查是否有中断请求"""
        with self._lock:
            requested = self._interrupt_requested
            self._interrupt_requested = False
            return requested
    
    def should_refresh(self) -> bool:
        """
        判断是否应该刷新界面（核心防刷屏逻辑）
        
        防刷屏规则：
        - 正在等待用户输入时 → 绝对禁止刷新
        - 只有AI生成时 → 允许刷新
        """
        if not self._refresh_enabled:
            return False
        
        # 防刷屏：等待输入时绝对禁止刷新
        if self.is_waiting_input():
            return False
            
        return self.is_generating()
    
    def print_status(self, message: str, style: str = "dim"):
        """打印状态信息（线程安全，防刷屏）"""
        if self.is_waiting_input():
            # 等待输入时不打印状态（防刷屏）
            return
            
        if self.console:
            self.console.print(f"[{style}]{message}[/{style}]")
        else:
            print(message)
    
    def safe_input(self, context: str, prompt_text: str, 
                  instructions: str = None, validation_func=None,
                  default: str = None) -> str:
        """
        安全输入函数（完整防刷屏版本）
        
        这是程序中所有用户输入的唯一入口！
        
        关键特性：
        1. 视觉上与常规输出明显区分
        2. 提供上下文和格式指导
        3. 严格防刷屏：输入期间完全阻塞所有刷新操作
        4. 可选的验证逻辑
        5. 默认值支持
        """
        self.set_state("waiting_input")
        try:
            return self._input_prompt_mgr.prompt(
                context=context,
                prompt_text=prompt_text,
                instructions=instructions,
                validation_func=validation_func,
                default=default
            )
        finally:
            self.set_state("idle")
    
    def safe_confirm(self, context: str, question: str,
                    default: bool = False, danger: bool = False) -> bool:
        """
        安全确认函数（防刷屏版本）
        """
        self.set_state("waiting_input")
        try:
            return self._input_prompt_mgr.confirm(
                context=context,
                question=question,
                default=default,
                danger=danger
            )
        finally:
            self.set_state("idle")


class SessionSwitcher:
    """
    会话切换管理器 (v5.3 新增)
    
    功能：
    - 会话列表浏览与选择
    - 无缝上下文切换
    - 数据完整性保障
    - 操作指引提示
    """
    
    def __init__(self, base_dir: str = "stories"):
        self.base_dir = Path(base_dir)
        self.console = RichConsole() if RICH_AVAILABLE else None
        self._current_session_id: Optional[str] = None
        
    def list_sessions(self) -> list:
        """获取所有可用会话列表"""
        sessions = []
        if not self.base_dir.exists():
            return sessions
            
        for item in self.base_dir.iterdir():
            if item.is_dir():
                node_file = item / "_story_node.json"
                if node_file.exists():
                    try:
                        with open(node_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            sessions.append({
                                'id': item.name,
                                'title': data.get('title', '未命名'),
                                'genre': data.get('genre', ''),
                                'chapters': data.get('total_chapters', 0),
                                'words': data.get('total_words', 0),
                                'updated': data.get('last_updated', '')
                            })
                    except:
                        pass
                        
        return sorted(sessions, key=lambda x: x['updated'], reverse=True)
    
    def show_session_list(self, show_hint: bool = True):
        """显示会话列表（带操作指引）"""
        sessions = self.list_sessions()
        
        if not sessions:
            if self.console:
                self.console.print("[yellow]⚠️ 暂无已保存的故事会话[/yellow]")
            else:
                print("⚠️ 暂无已保存的故事会话")
            return []
            
        if self.console:
            from rich.table import Table
            
            table = Table(show_header=True, title="📚 故事会话列表")
            table.add_column("#", style="cyan", width=4)
            table.add_column("ID", style="dim", width=25)
            table.add_column("标题", style="bold")
            table.add_column("类型", width=10)
            table.add_column("章节", width=6)
            table.add_column("字数", width=8)
            
            for i, s in enumerate(sessions[:15], 1):
                table.add_row(
                    str(i),
                    s['id'][:23] + "..." if len(s['id']) > 23 else s['id'],
                    s['title'][:30],
                    s['genre'] or "-",
                    str(s['chapters']),
                    f"{s['words']}字"
                )
                
            self.console.print(table)
        else:
            print("\n📚 故事会话列表:")
            print("-" * 60)
            for i, s in enumerate(sessions[:15], 1):
                print(f"  {i}. {s['id']}")
                print(f"     {s['title']} | {s['chapters']}章 | {s['words']}字")
                
        if show_hint and sessions:
            self._show_switch_hint(sessions)
            
        return sessions
    
    def _show_switch_hint(self, sessions: list):
        """显示会话切换操作指引"""
        hint_text = """
[dim]💡 会话切换操作指引:[/dim]
  [cyan]•[/cyan] 使用 [bold]--resume ID[/bold] 启动时恢复指定会话
  [cyan]•[/cyan] 在创作过程中输入 [bold]switch[/bold] 或 [bold]sw[/bold] 可切换会话
  [cyan]•[/cyan] 输入 [bold]list[/bold] 或 [bold]ls[/bold] 查看所有会话
  [cyan]•[/cyan] 最近更新的会话显示在最前面
"""
        if self.console:
            self.console.print(hint_text)
        else:
            print(hint_text)
    
    def get_session_by_index(self, index: int, sessions: list = None) -> Optional[str]:
        """通过索引获取会话ID"""
        if sessions is None:
            sessions = self.list_sessions()
        if 1 <= index <= len(sessions):
            return sessions[index-1]['id']
        return None
    
    def validate_session(self, session_id: str) -> bool:
        """验证会话是否存在且完整"""
        session_path = self.base_dir / session_id
        if not session_path.exists():
            return False
            
        required_files = ['_story_node.json', 'info', 'novel']
        for f in required_files:
            if not (session_path / f).exists():
                return False
                
        return True


class InterruptHandler:
    """
    中断处理器 (v5.3 新增)
    
    功能：
    - 信号捕获（SIGINT/Ctrl+C）
    - 优雅中断流程
    - 状态保存与恢复
    - 平滑过渡动画
    """
    
    def __init__(self, display_ctrl: SmartDisplayController = None):
        self.display = display_ctrl
        self.console = RichConsole() if RICH_AVAILABLE else None
        self._original_handler = None
        self._interrupt_count = 0
        self._last_interrupt_time = 0
        self._graceful_shutdown = False
        
    def setup(self):
        """设置中断信号处理"""
        self._original_handler = signal.signal(
            signal.SIGINT,
            self._handle_interrupt
        )
        
    def _handle_interrupt(self, signum, frame):
        """处理中断信号"""
        current_time = datetime.now().timestamp()
        time_diff = current_time - self._last_interrupt_time
        
        if time_diff < 1.0:
            self._interrupt_count += 1
        else:
            self._interrupt_count = 1
            
        self._last_interrupt_time = current_time
        
        if self._interrupt_count >= 2:
            self._force_exit()
        else:
            self._graceful_interrupt()
            
    def _graceful_interrupt(self):
        """优雅中断（第一次Ctrl+C）"""
        if self.display:
            self.display.request_interrupt()
            
        if self.console:
            self.console.print("\n[yellow]⏸️ 检测到中断请求...[/yellow]")
            self.console.print("[dim]   再次按 Ctrl+C 强制退出[/dim]\n")
        else:
            print("\n⏸️ 检测到中断请求...")
            print("   再次按 Ctrl+C 强制退出\n")
            
    def _force_exit(self):
        """强制退出（第二次Ctrl+C）"""
        if self.console:
            self.console.print("\n[red]❌ 用户强制退出[/red]")
        else:
            print("\n❌ 用户强制退出")
            
        sys.exit(130)
        
    def restore(self):
        """恢复原始信号处理"""
        if self._original_handler:
            signal.signal(signal.SIGINT, self._original_handler)


def print_banner_v53():
    """打印 v5.3 版本横幅"""
    banner = """
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║     🚀 WAgent v5.3 - 智能交互故事创作系统                     ║
║                                                               ║
║     ⚡ 智能刷新 | 🔄 无缝切换 | ⏸️ 随时打断 | 🎯 精准控制 ║
║     🔒 约束保障 | 📋 审计跟踪 | 💾 自动保存 | ↩️ 回滚恢复 ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
"""
    if console:
        console.print(banner)
    else:
        print(banner)


def quick_validation() -> bool:
    """快速环境验证（v5.3 优化版）"""
    print("\n⚡ WAgent v5.3 环境验证\n")
    
    checks = [
        ("Python 3.8+", sys.version_info >= (3, 8)),
        ("配置文件 (.env)", os.path.exists('.env')),
        ("langchain", _safe_import('langchain')),
        ("pydantic", _safe_import('pydantic')),
        ("aiohttp", _safe_import('aiohttp')),
        ("rich", _safe_import('rich')),
        ("导演AI引擎", _check_module_exists('wagent.engines.director')),
        ("研究员AI引擎", _check_module_exists('wagent.engines.researcher')),
        ("作家AI引擎", _check_module_exists('wagent.engines.writer')),
        ("约束管理系统", _check_module_exists('wagent.constraint_manager')),
        ("会话管理器", _check_module_exists('wagent.story_session')),
        ("主控制器", _check_module_exists('wagent.controller')),
    ]
    
    passed = 0
    for name, ok in checks:
        icon = "✅" if ok else "❌"
        print(f"  {icon} {name}")
        if ok: passed += 1
    
    api_keys = [
        ('DOUBAO_API_KEY', '豆包/Doubao'),
        ('DEEPSEEK_API_KEY', 'DeepSeek'),
        ('DASHSCOPE_API_KEY', '通义千问/Qwen')
    ]
    
    print("\n  API Keys:")
    for var, name in api_keys:
        v = os.getenv(var, '')
        masked = v[:8]+"..." if len(v)>8 else (v or "(未设置)")
        configured = bool(v)
        icon = "✅" if configured else "⚠️"
        print(f"  {icon} {var}: {masked}")
        if configured: passed += 1
    
    total = len(checks) + len(api_keys)
    rate = passed / total * 100 if total > 0 else 0
    
    print(f"\n{'='*50}")
    print(f"  结果: {passed}/{total} 通过 ({rate:.1f}%)")
    
    if rate >= 90:
        print("  🎉 系统完全就绪！")
        return True
    elif rate >= 70:
        print("  ✅ 系统基本就绪（部分功能受限）")
        return True
    else:
        print("  ❌ 存在问题，请检查依赖安装")
        return False


def _safe_import(module_name):
    """安全导入检查"""
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False

def _check_module_exists(module_path):
    """检查模块路径是否存在"""
    try:
        __import__(module_path)
        return True
    except ImportError:
        file_path = module_path.replace('.', '/') + '.py'
        return os.path.exists(file_path)


def show_config():
    """显示功能配置（v5.3 增强版）"""
    try:
        from wagent.config import FeatureFlags
        
        flags = FeatureFlags.from_env()
        
        if console:
            from rich.table import Table
            
            table = Table(show_header=True, title="⚙️ WAgent v5.3 功能配置")
            table.add_column("功能项", style="cyan", width=28)
            table.add_column("状态", width=8)
            table.add_column("值", style="dim")
            
            config_items = [
                ("实时智能刷新", flags.enable_realtime_refresh,
                 f"{flags.refresh_interval}s间隔"),
                ("文本规范化", flags.enable_text_normalization, ""),
                ("平滑过渡效果", flags.smooth_transition, ""),
                ("大小写不敏感命令", flags.case_insensitive_commands, ""),
                ("自动重试机制", flags.auto_retry_on_error, 
                 f"{flags.max_retry_attempts}次"),
                ("优雅降级模式", flags.graceful_degradation, ""),
            ]
            
            for name, enabled, value in config_items:
                status = "✅" if enabled else "❌"
                val_str = value if value else ("启用" if enabled else "禁用")
                table.add_row(name, status, val_str)
                
            console.print(table)
            console.print("\n[dim]💡 提示: 使用命令行参数可临时覆盖上述配置[/dim]")
        else:
            print("\n⚙️ WAgent v5.3 功能配置:")
            for k, v in flags.to_dict().items():
                status = "✅" if v else "❌"
                print(f"  {status} {k}: {v}")
                
    except Exception as e:
        print(f"❌ 无法加载配置: {e}")


def run_tests():
    """运行测试套件（v5.3 更新）"""
    if console:
        console.print("[bold]🧪 WAgent v5.3 测试模式[/bold]\n")
    else:
        print("\n🧪 WAgent v5.3 测试模式\n")
    
    test_file = Path(__file__).parent / "test_v52_system.py"
    if test_file.exists():
        import subprocess
        result = subprocess.run([sys.executable, str(test_file)], capture_output=False)
        return result.returncode == 0
    else:
        print("⚠️ 测试文件不存在: test_v52_system.py")
        return False


def interactive_session_switch(session_switcher: SessionSwitcher):
    """
    交互式会话切换界面（v5.3 新增）
    
    提供友好的会话选择和切换体验
    """
    _console = RichConsole() if RICH_AVAILABLE else None
    
    while True:
        sessions = session_switcher.show_session_list(show_hint=False)
        
        if not sessions:
            if console:
                console.print("[yellow]没有可用的会话，按回车返回[/yellow]")
            else:
                print("没有可用的会话，按回车返回")
            input()
            return None
            
        console.print("\n[cyan]请选择操作:[/cyan]" if console else "\n请选择操作:")
        console.print("  [bold]1-N[/bold] - 选择对应编号的会话") if console else print("  1-N - 选择对应编号的会话")
        console.print("  [bold]q/quit[/bold] - 返回主菜单") if console else print("  q/quit - 返回主菜单")
        
        choice = input("\n> ").strip().lower()
        
        if choice in ['q', 'quit', '']:
            return None
            
        if choice.isdigit():
            idx = int(choice)
            session_id = session_switcher.get_session_by_index(idx, sessions)
            if session_id:
                if session_switcher.validate_session(session_id):
                    return session_id
                else:
                    if console:
                        console.print(f"[red]❌ 会话数据不完整: {session_id}[/red]")
                    else:
                        print(f"❌ 会话数据不完整: {session_id}")
            else:
                if console:
                    console.print(f"[yellow]⚠️ 无效的编号: {idx}[/yellow]")
                else:
                    print(f"⚠️ 无效的编号: {idx}")
        else:
            if console:
                console.print(f"[yellow]⚠️ 无效输入，请输入数字编号或 q 退出[/yellow]")
            else:
                print("⚠️ 无效输入，请输入数字编号或 q 退出")


def show_enterprise_session_list(mgr):
    """
    显示企业级会话列表（v2.0 增强版）
    
    包含完整的状态信息、隔离状态、安全令牌等
    """
    _console = RichConsole() if RICH_AVAILABLE else None
    
    status = mgr.get_system_status()
    all_sessions = mgr.get_all_sessions(include_terminated=True)
    
    if _console:
        from rich.table import Table
        from rich.panel import Panel
        
        _console.print("\n" + "=" * 70)
        _console.print("[bold cyan]🔐 企业级会话管理系统 v2.0[/bold cyan]")
        _console.print("=" * 70)
        
        # 系统概览
        overview = f"""
[dim]系统概览:[/dim]
  [green]●[/green] 活跃会话: {status['active_sessions']}
  [yellow]●[/yellow] 空闲会话: {status['idle_sessions']}
  [red]●[/red] 过期会话: {status['expired_sessions']}
  [cyan]●[/cyan] 当前会话: {status.get('current_session_id', '无') or '无'}
  [dim]监控: {'运行中' if status['monitor_running'] else '已停止'} | 自动清理: {'启用' if status['auto_cleanup_enabled'] else '禁用'}[/dim]
"""
        _console.print(Panel(overview, title="📊 系统状态"))
        
        # 会话列表表格
        table = Table(show_header=True, title="📋 会话列表")
        table.add_column("#", style="cyan", width=4)
        table.add_column("会话ID", style="dim", width=22)
        table.add_column("状态", width=10)
        table.add_column("用户", width=12)
        table.add_column("年龄", width=8)
        table.add_column("空闲", width=8)
        table.add_column("锁定", width=6)
        table.add_column("数据大小", width=10)
        
        state_icons = {
            'active': '[green]活跃[/green]',
            'idle': '[yellow]空闲[/yellow]',
            'suspended': '[blue]挂起[/blue]',
            'expired': '[red]过期[/red]',
            'terminated': '[dim]终止[/dim]',
            'error': '[red]错误[/red]',
            'created': '[dim]创建[/dim]'
        }
        
        for i, session in enumerate(all_sessions[:20], 1):
            state_icon = state_icons.get(session.state.value, str(session.state.value))
            lock_icon = '🔒' if session.is_locked else '✓'
            
            age_min = int(session.age_seconds / 60)
            idle_min = int(session.idle_seconds / 60)
            data_kb = f"{(session.data_store.size_bytes / 1024):.1f}KB" if session.data_store else "N/A"
            
            user_id = session.metadata.user_id if session.metadata else "unknown"
            
            table.add_row(
                str(i),
                session.session_id[:20] + ("..." if len(session.session_id) > 20 else ""),
                state_icon,
                user_id[:10],
                f"{age_min}m",
                f"{idle_min}m",
                lock_icon,
                data_kb
            )
        
        _console.print(table)
        
        if len(all_sessions) > 20:
            _console.print(f"\n[dim]... 还有 {len(all_sessions)-20} 个会话未显示[/dim]")
        
    else:
        print("\n" + "=" * 70)
        print("🔐 企业级会话管理系统 v2.0")
        print("=" * 70)
        print(f"\n总会话: {len(all_sessions)} | 活跃: {status['active_sessions']} | 空闲: {status['idle_sessions']}")
        
        for i, session in enumerate(all_sessions[:15], 1):
            print(f"  {i}. {session.session_id}")
            print(f"     状态: {session.state.value} | 用户: {session.metadata.user_id or '?'}")


def handle_runtime_session_command(command_str: str, mgr, wagent_instance=None):
    """
    处理运行时会话管理命令
    
    支持的命令：
    - session list          - 列出所有会话
    - session info          - 当前会话详情
    - session switch <id>   - 切换到指定会话
    - session new           - 创建新会话并切换
    - session terminate <id>- 终止指定会话
    - session status        - 系统状态概览
    
    Returns:
        (是否处理了命令, 结果消息)
    """
    _console = RichConsole() if RICH_AVAILABLE else None
    
    parts = command_str.strip().split()
    if not parts or parts[0].lower() != 'session':
        return False, ""
    
    cmd = parts[1].lower() if len(parts) > 1 else ""
    args = parts[2:] if len(parts) > 2 else []
    
    try:
        if cmd == 'list' or cmd == 'ls':
            show_enterprise_session_list(mgr)
            return True, "已显示会话列表"
        
        elif cmd == 'info' or cmd == 'status':
            current = mgr.get_current_session()
            if current:
                report = current.get_status_report()
                
                if _console:
                    from rich.panel import Panel
                    _console.print("\n[bold cyan]📊 当前会话详情[/bold cyan]")
                    _console.print(Panel(
                        f"""
[dim]基本信息:[/dim]
  [bold]会话ID:[/bold] {report['session_id']}
  [bold]状态:[/bold] {report['state']}
  [bold]有效:[/bold] {'✅ 是' if report['is_valid'] else '❌ 否'}
  [bold]锁定:[/bold] {'🔒 是' if report['is_locked'] else '✓ 否'}

[dim]时间信息:[/dim]
  [bold]创建时间:[/bold] {report['created_at']}
  [bold]最后访问:[/bold] {report['last_accessed_at']}
  [bold]过期时间:[/bold] {report['expires_at']}
  [bold]会话年龄:[/bold] {int(report['age_seconds'])}秒 ({int(report['age_seconds']/60)}分钟)
  [bold]空闲时间:[/bold] {int(report['idle_seconds'])}秒 ({int(report['idle_seconds']/60)}分钟)

[dim]数据与安全:[/dim]
  [bold]数据大小:[/bold] {report['data_size_kb']} KB
  [bold]数据完整性:[/bold] {'✅ 正常' if report['data_integrity_ok'] else '❌ 损坏'}
  [bold]事件记录:[/bold] {report['events_count']} 条
  [bold]令牌有效:[/bold] {'✅ 是' if report['token_valid'] else '❌ 否'}
                        """,
                        title=f"会话: {current.session_id[:16]}..."
                    ))
                else:
                    print(f"\n当前会话: {current.session_id}")
                    print(f"状态: {report['state']}")
                    print(f"年龄: {int(report['age_seconds'])}秒 | 空闲: {int(report['idle_seconds'])}秒")
                    
                return True, f"当前会话: {current.session_id}"
            else:
                msg = "当前没有活跃的会话。使用 'session new' 创建新会话"
                if _console:
                    _console.print(f"[yellow]{msg}[/yellow]")
                else:
                    print(msg)
                return True, msg
        
        elif cmd == 'switch' or cmd == 'sw':
            if not args:
                return False, "需要指定会话ID: session switch <session_id>"
            
            target_id = args[0]
            success, error = mgr.switch_to(target_id)
            
            if success:
                msg = f"✅ 已切换到会话: {target_id}"
                if wagent_instance and hasattr(wagent_instance, '_enterprise_session_mgr'):
                    wagent_instance._enterprise_session_mgr = mgr
            else:
                msg = f"❌ 切换失败: {error or '未知错误'}"
            
            if _console:
                color = "green" if success else "red"
                _console.print(f"[{color}]{msg}[/{color}]")
            else:
                print(msg)
            
            return True, msg
        
        elif cmd == 'new':
            metadata = {}
            if args:
                metadata['name'] = ' '.join(args)
            
            new_session = mgr.switch_to_new(metadata=metadata)
            msg = f"✅ 已创建并切换到新会话: {new_session.session_id}"
            
            if _console:
                _console.print(f"[green]{msg}[/green]")
            else:
                print(msg)
            
            return True, msg
        
        elif cmd == 'terminate' or cmd == 'kill':
            if not args:
                return False, "需要指定会话ID: session terminate <session_id>"
            
            target_id = args[0]
            success = mgr.terminate_session(target_id)
            
            if success:
                msg = f"✅ 已终止会话: {target_id}"
            else:
                msg = f"❌ 终制失败: 会话不存在或已被终止"
            
            if _console:
                color = "green" if success else "red"
                _console.print(f"[{color}]{msg}[/{color}]")
            else:
                print(msg)
            
            return True, msg
        
        elif cmd == 'help' or cmd == '':
            help_text = """
[dim]会话管理命令帮助:[/dim]

[cyan]session list[/cyan]         - 列出所有会话（含详细状态）
[cyan]session info[/cyan]         - 显示当前会话详细信息
[cyan]session switch <id>[/cyan]   - 切换到指定会话
[cyan]session new [名称][/cyan]     - 创建新会话并自动切换
[cyan]session terminate <id>[/cyan]- 终止指定会话
[cyan]session status[/cyan]       - 系统状态概览

[dim]示例:[/dim]
  session switch sess_abc123
  session new 我的新故事
  session terminate sess_old001

[dim]提示: 所有会话操作都会被记录审计日志[/dim]
"""
            if _console:
                _console.print(help_text)
            else:
                print(help_text)
            
            return True, "已显示帮助"
        
        else:
            msg = f"未知命令: session {cmd}。输入 'session help' 查看可用命令"
            if _console:
                _console.print(f"[red]{msg}[/red]")
            else:
                print(msg)
            return True, msg
            
    except Exception as e:
        error_msg = f"❌ 执行命令时出错: {str(e)}"
        if _console:
            _console.print(f"[red]{error_msg}[/red]")
        else:
            print(error_msg)
        return True, error_msg


def main():
    """
    主函数 (v5.3 升级版)
    
    新增特性：
    - 智能刷新控制
    - 会话管理增强
    - 中断处理
    - 清理冗余代码
    """
    
    parser = argparse.ArgumentParser(
        description="WAgent v5.3 - 智能交互故事创作系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python wagent.py                      # 启动交互式创作（默认）
  python wagent.py --quick               # 快速验证环境
  python wagent.py --test                # 运行测试套件
  python wagent.py --show-config         # 显示功能配置
  python wagent.py --list                # 列出所有已保存的故事
  python wagent.py --resume STORY_ID     # 恢复指定会话
  
企业级会话管理 (v2.0):
  python wagent.py --session-list        # 列出所有会话（含详细状态）
  python wagent.py --session-info         # 显示当前会话详细信息

高级选项:
  --no-refresh          禁用智能刷新
  --no-normalize        禁用文本规范化
  --refresh-interval N  自定义刷新间隔（秒）

运行时会话命令 (在交互模式中输入):
  session list          - 列出所有会话
  session info          - 当前会话详情
  session switch <id>   - 切换到指定会话
  session new [名称]     - 创建新会话并切换
  session terminate <id>- 终止指定会话
  session help           - 会话命令帮助

环境变量:
  WAGENT_REFRESH=true|false      启用/禁用刷新
  WAGENT_NORMALIZE=true|false    启用/禁用规范化
"""
    )
    
    parser.add_argument('--quick','-q',action='store_true',
                       help='快速验证环境')
    parser.add_argument('--test','-t',action='store_true',
                       help='运行测试套件')
    parser.add_argument('--show-config',action='store_true',
                       help='显示当前功能配置并退出')
    parser.add_argument('--no-refresh',action='store_true',
                       help='禁用智能刷新')
    parser.add_argument('--no-normalize',action='store_true',
                       help='禁用字符转换')
    parser.add_argument('--refresh-interval',type=float,default=None,
                       help='刷新间隔时间（秒，默认3.0）')
    parser.add_argument('--resume','-r',type=str,default=None,
                       metavar='STORY_ID',
                       help='恢复指定故事ID的会话继续创作')
    parser.add_argument('--list','-l',action='store_true',
                       help='列出所有已保存的故事')
    parser.add_argument('--switch', '-s', action='store_true',
                       help='交互式会话切换模式')
    parser.add_argument('--session-info', action='store_true',
                       help='显示当前会话详细信息')
    parser.add_argument('--session-list', action='store_true',
                       help='列出所有会话（含状态）')
    
    args = parser.parse_args()
    start_time = datetime.now()
    
    # 初始化核心组件
    display_ctrl = SmartDisplayController()
    session_switcher = SessionSwitcher()
    interrupt_handler = InterruptHandler(display_ctrl)
    
    # 初始化企业级会话管理系统 (v2.0)
    try:
        from wagent.session_manager import SessionManager, create_session_manager
        enterprise_session_mgr = SessionManager(base_dir="sessions", auto_cleanup=True)
    except ImportError:
        enterprise_session_mgr = None
    
    # 处理 --session-list 参数（企业级会话列表）
    if args.session_list and enterprise_session_mgr:
        show_enterprise_session_list(enterprise_session_mgr)
        return
    
    # 处理 --list 参数
    if args.list:
        session_switcher.show_session_list()
        return
    
    # 处理 --switch 参数（交互式会话切换）
    if args.switch:
        selected_session = interactive_session_switch(session_switcher)
        if selected_session:
            args.resume = selected_session
        else:
            return
    
    if args.quick:
        quick_validation()
        return
    
    if args.test:
        success = run_tests()
        sys.exit(0 if success else 1)
        
    if args.show_config:
        show_config()
        return
    
    # 加载功能配置
    try:
        from wagent.config import FeatureFlags as FF
        flags = FF.from_env()
        
        if args.no_refresh:
            flags.enable_realtime_refresh = False
        if args.no_normalize:
            flags.enable_text_normalization = False
        if args.refresh_interval is not None:
            flags.refresh_interval = max(1.0, min(60.0, args.refresh_interval))
    except ImportError:
        flags = None
    
    # 显示启动信息
    print_banner_v53()
    
    if console:
        console.print(f"[bold green]🚀 WAgent v5.3 启动中...[/bold green]")
        if flags:
            if not flags.enable_realtime_refresh:
                console.print("[dim]   ℹ️ 智能刷新已禁用[/dim]")
            console.print(f"[dim]   ℹ️ 刷新策略: AI生成时刷新，输入时静止[/dim]")
        console.print()
    else:
        print("🚀 WAgent v5.3 启动中...")
        print("   ℹ️ 刷新策略: AI生成时刷新，输入时静止\n")
    
    # 设置中断处理
    interrupt_handler.setup()
    
    # 导入并启动WAgent控制器
    try:
        from wagent.controller import WAgent
        
        wagent = WAgent(flags=flags) if flags else WAgent()
        
        # 注入智能显示控制器到WAgent实例（如果支持）
        if hasattr(wagent, '_smart_display'):
            wagent._smart_display = display_ctrl
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                loop.run_until_complete(
                    wagent.initialize(resume_story_id=args.resume)
                )
                
                # 设置初始状态为等待输入
                display_ctrl.set_state("waiting_input")
                
                loop.run_until_complete(wagent.run_session())
                
            except KeyboardInterrupt:
                if console:
                    console.print("\n[yellow]⏸️ 用户中断创作[/yellow]")
                else:
                    print("\n⏸️ 用户中断创作")
                    
            finally:
                loop.close()
                
        except Exception as e:
            if console:
                console.print(f"\n[red]❌ 运行错误: {e}[/red]")
            else:
                print(f"\n❌ 运行错误: {e}")
            
            if flags and getattr(flags, 'graceful_degradation', True):
                if console:
                    console.print("[dim]系统已优雅降级，请查看日志获取详情[/dim]")
            else:
                import traceback
                traceback.print_exc()
                
    except ImportError as e:
        if console:
            console.print(f"[red]❌ 模块导入失败: {e}[/red]")
            console.print("[dim]请确保所有依赖已安装: pip install -r requirements.txt[/dim]")
        else:
            print(f"❌ 模块导入失败: {e}")
            print("请确保所有依赖已安装")
    finally:
        interrupt_handler.restore()
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        if console:
            console.print(f"\n[dim]⏱️ 总运行时长: {duration:.1f}s[/dim]")
            console.print("[dim]感谢使用 WAgent v5.3! 👋[/dim]\n")
        else:
            print(f"\n⏱️ 总运行时长: {duration:.1f}s")
            print("感谢使用 WAgent v5.3! 👋\n")


if __name__ == "__main__":
    main()
