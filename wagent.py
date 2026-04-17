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
    RICH_AVAILABLE = True
    console = RichConsole()
except ImportError:
    RichConsole = Panel = Markdown = None
    RICH_AVAILABLE = False
    console = None


class SmartDisplayController:
    """
    智能显示控制器 (v5.3 新增)
    
    核心功能：
    - 状态感知：区分"AI生成中"和"等待用户输入"
    - 智能刷新：仅在AI生成时触发界面更新
    - 输入保护：用户输入时保持界面静止
    - 打断支持：支持优雅中断当前操作
    """
    
    def __init__(self):
        self.console = RichConsole() if RICH_AVAILABLE else None
        self._state = "idle"  # idle/generating/waiting_input/interrupted
        self._refresh_enabled = True
        self._interrupt_requested = False
        self._lock = threading.Lock()
        
    def set_state(self, state: str):
        """设置当前状态"""
        with self._lock:
            self._state = state
            
    def is_generating(self) -> bool:
        """检查是否正在AI生成"""
        return self._state == "generating"
    
    def is_waiting_input(self) -> bool:
        """检查是否在等待用户输入"""
        return self._state == "waiting_input"
    
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
        """判断是否应该刷新界面（核心逻辑）"""
        if not self._refresh_enabled:
            return False
        return self.is_generating()
    
    def print_status(self, message: str, style: str = "dim"):
        """打印状态信息（线程安全）"""
        if self.console:
            self.console.print(f"[{style}]{message}[/{style}]")
        else:
            print(message)


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
  
高级选项:
  --no-refresh          禁用智能刷新
  --no-normalize        禁用文本规范化
  --refresh-interval N  自定义刷新间隔（秒）

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
    
    args = parser.parse_args()
    start_time = datetime.now()
    
    # 初始化核心组件
    display_ctrl = SmartDisplayController()
    session_switcher = SessionSwitcher()
    interrupt_handler = InterruptHandler(display_ctrl)
    
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
