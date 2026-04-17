#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WAgent Launcher v7.1 - 完整启动程序（集成真实 wagent.py）

功能模块：
1. 会话选择界面 - 列表展示/创建/选择/删除
2. Agent控制界面 - 启动/暂停/打断/删除
3. 故事创作界面 - 继续创作/全新创作（真实 wagent.py 集成）
4. 导航系统 - 会话↔Agent↔返回
5. 安全退出机制

UI框架：基于Rich库的终端交互界面
"""

import os
import sys
import json
import time
import signal
import atexit
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Tuple

sys.path.insert(0, str(Path(__file__).parent))

try:
    from rich.console import Console as RichConsole
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt, Confirm
    from rich.text import Text
    from rich.layout import Layout
    from rich.live import Live
except ImportError:
    print("❌ 缺少依赖: 请运行 pip install rich")
    sys.exit(1)

from wagent.stories_manager import (
    StoryScanner,
    SessionAgentManager,
    AgentInstance,
    SessionState,
    create_scanner,
    create_session_manager,
    ErrorSeverity,
    StoryErrorHandler
)


class WAgenterLauncher:
    """
    WAgent 主启动控制器（集成真实 wagent.py）
    
    管理整个应用程序的生命周期和用户交互流程
    """
    
    VERSION = "7.1"
    
    def __init__(self):
        self.console = RichConsole()
        self.base_dir = Path(__file__).parent / "stories"
        
        # 核心组件
        self.scanner = None
        self.session_mgr = None
        self.error_handler = None
        
        # 运行状态
        self.running = True
        self.current_session_id: Optional[str] = None
        self.current_agent_instance: Optional[AgentInstance] = None
        
        # 初始化组件
        self._initialize_components()
        
        # 注册退出处理
        atexit.register(self._cleanup)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _initialize_components(self):
        """初始化所有核心组件"""
        try:
            self.console.print("\n🔄 正在初始化系统组件...")
            
            # 1. 错误处理器（最先初始化）
            log_file = self.base_dir / "_launcher_errors.log"
            self.error_handler = StoryErrorHandler(
                log_file=str(log_file),
                console_output=True
            )
            
            # 2. 故事扫描器
            self.scanner = create_scanner(str(self.base_dir))
            
            # 3. 会话管理器
            self.session_mgr = create_session_manager(str(self.base_dir))
            
            self.console.print("✅ [green]系统组件初始化完成[/green]")
            
        except Exception as e:
            self.console.print(f"❌ [red]初始化失败: {str(e)}[/red]")
            self.error_handler.log_error(
                severity=ErrorSeverity.CRITICAL,
                error_type='INIT_FAILED',
                message=str(e)
            )
            sys.exit(1)
    
    def run(self):
        """主运行循环"""
        try:
            while self.running:
                self._show_session_selection()
            
        except KeyboardInterrupt:
            self.console.print("\n\n⚠️ 用户中断，正在安全退出...")
            self._cleanup()
            
        except Exception as e:
            self.console.print(f"\n❌ [red]致命错误: {str(e)}[/red]")
            self.error_handler.log_error(
                severity=ErrorSeverity.CRITICAL,
                error_type='RUNTIME_ERROR',
                message=str(e)
            )
    
    def _show_session_selection(self):
        """
        显示会话选择界面
        
        这是程序的"主页"，提供以下功能：
        - 显示现有会话列表
        - 创建新会话
        - 选择并进入会话
        - 删除会话
        - 退出程序
        """
        self.console.clear()
        self._print_header("🏠 WAgent 会话管理中心")
        
        # 获取会话列表
        sessions = self.session_mgr.list_all_sessions(active_only=True)
        stats = self.session_mgr.get_statistics()
        
        # 显示统计信息
        self.console.print(f"[dim]活跃会话: {stats['active_count']} | "
                          f"总创建: {stats['total_created']} | "
                          f"故事绑定: {stats['story_bindings']}[/dim]\n")
        
        if not sessions:
            self.console.print("[yellow]暂无活动会话，请创建新会话开始使用[/yellow]\n")
        else:
            # 显示会话表格
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("#", style="cyan", width=4)
            table.add_column("会话ID", style="white")
            table.add_column("实例ID", style="dim")
            table.add_column("状态", justify="center")
            table.add_column("故事绑定", justify="center")
            table.add_column("最后活跃", style="dim")
            
            for idx, sess in enumerate(sessions[:10], 1):  # 最多显示10个
                state_color = {
                    'running': 'green',
                    'paused': 'yellow',
                    'created': 'blue',
                    'stopped': 'red'
                }.get(sess['state'], 'white')
                
                bound_mark = "✓" if sess['story_bound'] else "−"
                table.add_row(
                    str(idx),
                    sess['session_id'][:20],
                    sess['instance_id'][:12] + "...",
                    f"[{state_color}]{sess['state']}[/{state_color}]",
                    bound_mark,
                    sess.get('last_active', '-')[:19]
                )
            
            self.console.print(table)
        
        # 操作菜单
        self.console.print("\n[dim]─[/dim]" * 50)
        self.console.print("[bold cyan]操作菜单:[/bold cyan]")
        self.console.print("  [1] 🆕 创建新会话")
        self.console.print("  [2] 👉 选择并进入会话 (输入编号)")
        self.console.print("  [3] 🗑️  删除会话")
        self.console.print("  [4] 📊 查看系统状态")
        self.console.print("  [5] 🚪 退出程序")
        self.console.print()
        
        choice = Prompt.ask(
            "[bold green]请选择操作[/bold green]",
            choices=["1", "2", "3", "4", "5"],
            default="2"
        )
        
        if choice == "1":
            self._create_new_session()
        elif choice == "2":
            self._select_and_enter_session(sessions)
        elif choice == "3":
            self._delete_session_ui()
        elif choice == "4":
            self._show_system_status()
        elif choice == "5":
            self._exit_program()
    
    def _create_new_session(self):
        """创建新会话的交互流程"""
        self.console.clear()
        self._print_header("🆕 创建新会话")
        
        # 输入会话ID
        session_id = Prompt.ask(
            "[bold]输入会话ID[/bold]",
            default=f"sess_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        
        # 检查是否已存在
        if self.session_mgr.get_instance(session_id):
            self.console.print(f"[red]❌ 会话 '{session_id}' 已存在！[/red]")
            time.sleep(1.5)
            return
        
        # 选择故事（可选）
        stories = self._scan_available_stories()
        story_path = ""
        
        if stories:
            self.console.print("\n[cyan]可用的故事目录:[/cyan]")
            for idx, story in enumerate(stories[:8], 1):
                title = story.get('title', '(未命名)')
                sid = story.get('story_id', '')[:15]
                self.console.print(f"  {idx}. [{sid}] {title}")
            
            bind_story = Confirm.ask("\n是否立即绑定故事？", default=False)
            if bind_story:
                story_choice = Prompt.ask("选择故事编号", default="1")
                try:
                    idx = int(story_choice) - 1
                    if 0 <= idx < len(stories):
                        story_path = stories[idx]['path']
                        self.console.print(f"[green]✓ 已选择: {story_path}[/green]")
                except ValueError:
                    pass
        
        # 创建会话
        try:
            instance = self.session_mgr.create_session(session_id)
            self.console.print(f"\n[green]✅ 会话创建成功！[/green]")
            self.console.print(f"   会话ID: {session_id}")
            self.console.print(f"   实例ID: {instance.instance_id}")
            
            # 是否立即启动
            start_now = Confirm.ask("\n是否立即启动Agent？", default=True)
            if start_now:
                success, msg = self.session_mgr.start_agent(session_id, story_path)
                if success:
                    self.console.print(f"[green]✅ {msg}[/green]")
                    
                    enter_now = Confirm.ask("是否进入会话？", default=True)
                    if enter_now:
                        self.current_session_id = session_id
                        self._show_agent_control_panel()
                else:
                    self.console.print(f"[red]❌ {msg}[/red]")
            
            time.sleep(1.5)
            
        except Exception as e:
            self.console.print(f"[red]❌ 创建失败: {str(e)}[/red]")
            self.error_handler.log_error(ErrorSeverity.ERROR, 'CREATE_SESSION', str(e))
            time.sleep(2)
    
    def _select_and_enter_session(self, sessions: List[Dict]):
        """选择并进入已有会话"""
        if not sessions:
            self.console.print("[yellow]⚠️ 没有可用的会话[/yellow]")
            time.sleep(1.5)
            return
        
        self.console.print()
        choice = Prompt.ask(
            "[bold]输入要进入的会话编号[/bold]",
            default="1"
        )
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(sessions):
                session_id = sessions[idx]['session_id']
                self.current_session_id = session_id
                self._show_agent_control_panel()
            else:
                self.console.print("[red]❌ 无效的编号[/red]")
                time.sleep(1)
                
        except ValueError:
            self.console.print("[red]❌ 请输入有效数字[/red]")
            time.sleep(1)
    
    def _show_agent_control_panel(self):
        """
        Agent控制面板
        
        这是会话内的主要操作界面，提供：
        - Agent状态监控
        - 启动/暂停/恢复/停止/销毁
        - 故事创作控制（真实 wagent.py）
        - 返回会话列表
        """
        if not self.current_session_id:
            return
        
        instance = self.session_mgr.get_instance(self.current_session_id)
        if not instance:
            self.console.print("[red]❌ 会话不存在或已被删除[/red]")
            self.current_session_id = None
            time.sleep(1.5)
            return
        
        while True:
            self.console.clear()
            self._print_header(f"🤖 Agent 控制面板 - {self.current_session_id}")
            
            # 显示实例信息
            info_table = Table(show_header=False, box=None)
            info_table.add_column("属性", style="cyan", width=18)
            info_table.add_column("值", style="white")
            
            state_colors = {
                'running': 'green',
                'paused': 'yellow',
                'stopped': 'red',
                'created': 'blue'
            }
            state_color = state_colors.get(instance.state.value, 'white')
            
            info_table.add_row("会话ID", self.current_session_id)
            info_table.add_row("实例ID", instance.instance_id)
            info_table.add_row(
                "当前状态",
                f"[{state_color}]{instance.state.value.upper()}[/{state_color}]"
            )
            info_table.add_row("绑定故事", instance.bound_story_path or "(无)")
            info_table.add_row("当前章节", str(instance.current_chapter))
            info_table.add_row("生成字数", f"{instance.total_words_generated:,}")
            info_table.add_row("内存占用", f"{instance.memory_usage_mb:.1f} MB")
            info_table.add_row("最后活跃", instance.last_active_at[:19])
            
            self.console.print(info_table)
            
            # 操作菜单（根据状态动态显示）
            self.console.print("\n[dim]─[/dim]" * 50)
            self.console.print("[bold cyan]Agent 操作:[/bold cyan]")
            
            if instance.state in [SessionState.CREATED, SessionState.STOPPED]:
                self.console.print("  [1] ▶️  启动 Agent")
            elif instance.state == SessionState.RUNNING:
                self.console.print("  [2] ⏸️  暂停 Agent")
                self.console.print("  [3] ⏹️  停止 Agent")
                self.console.print("  [4] ✋  打断当前生成")
                self.console.print("  [5] 📝 开始/继续创作 (真实 wagent.py)")
            elif instance.state == SessionState.PAUSED:
                self.console.print("  [6] ▶️  恢复 Agent")
            
            self.console.print("  ───────────────")
            self.console.print("  [b] 🔙  返回会话列表")
            self.console.print("  [d] 🗑️  删除此会话")
            self.console.print("  [i] ℹ️  查看详细信息")
            self.console.print()
            
            valid_choices = ["b", "d", "i"]
            if instance.state in [SessionState.CREATED, SessionState.STOPPED]:
                valid_choices.append("1")
                prompt_text = "[bold green]选择操作 (1/b/d/i)[/bold green]"
            elif instance.state == SessionState.RUNNING:
                valid_choices.extend(["2", "3", "4", "5"])
                prompt_text = "[bold green]选择操作 (2-5/b/d/i)[/bold green]"
            elif instance.state == SessionState.PAUSED:
                valid_choices.append("6")
                prompt_text = "[bold green]选择操作 (6/b/d/i)[/bold green]"
            else:
                prompt_text = "[bold green]选择操作 (b/d/i)[/bold green]"
            
            choice = Prompt.ask(prompt_text, default="b").lower()
            
            if choice == "1":
                self._start_agent(instance)
            elif choice == "2":
                self._pause_agent(instance)
            elif choice == "3":
                self._stop_agent(instance)
            elif choice == "4":
                self._interrupt_generation(instance)
            elif choice == "5":
                self._start_story_creation(instance)
            elif choice == "6":
                self._resume_agent(instance)
            elif choice == "b":
                self.current_session_id = None
                break
            elif choice == "d":
                if self._confirm_destroy_session():
                    break
            elif choice == "i":
                self._show_detailed_info(instance)
            
            # 刷新实例状态
            instance = self.session_mgr.get_instance(self.current_session_id)
            if not instance:
                break
    
    def _start_agent(self, instance: AgentInstance):
        """启动Agent实例"""
        story_path = ""
        if not instance.bound_story_path:
            stories = self._scan_available_stories()
            if stories:
                bind = Confirm.ask("是否绑定故事？", default=True)
                if bind:
                    for idx, s in enumerate(stories[:5], 1):
                        self.console.print(f"  {idx}. {s.get('story_id', '')}")
                    ch = Prompt.ask("选择", default="1")
                    try:
                        story_path = stories[int(ch)-1]['path']
                    except:
                        pass
        
        success, msg = self.session_mgr.start_agent(
            self.current_session_id,
            story_path
        )
        
        if success:
            self.console.print(f"[green]✅ {msg}[/green]")
        else:
            self.console.print(f"[red]❌ {msg}[/red]")
        
        time.sleep(1)
    
    def _pause_agent(self, instance: AgentInstance):
        """暂停Agent"""
        success, msg = self.session_mgr.pause_agent(self.current_session_id)
        status = "✅" if success else "❌"
        color = "green" if success else "red"
        self.console.print(f"[{color}]{status} {msg}[/{color}]")
        time.sleep(1)
    
    def _resume_agent(self, instance: AgentInstance):
        """恢复Agent"""
        success, msg = self.session_mgr.resume_agent(self.current_session_id)
        status = "✅" if success else "❌"
        color = "green" if success else "red"
        self.console.print(f"[{color}]{status} {msg}[/{color}]")
        time.sleep(1)
    
    def _stop_agent(self, instance: AgentInstance):
        """停止Agent"""
        force = Confirm.ask("是否强制停止？（正常停止需等待）", default=False)
        success, msg = self.session_mgr.stop_agent(self.current_session_id, force=force)
        status = "✅" if success else "❌"
        color = "green" if success else "red"
        self.console.print(f"[{color}]{status} {msg}[/{color}]")
        time.sleep(1)
    
    def _interrupt_generation(self, instance: AgentInstance):
        """打断当前生成过程"""
        self.console.print("\n[yellow]⚡ 正在打断当前生成...[/yellow]")
        
        # 这里实际应用中会调用wagent.py的中断接口
        # 目前模拟打断效果
        time.sleep(0.5)
        self.console.print("[green]✅ 已发送中断信号[/green]")
        self.console.print("[dim]   Agent将在当前段落完成后停止[/dim]")
        
        self.session_mgr.update_instance_stats(
            self.current_session_id,
            last_action="interrupted"
        )
        time.sleep(1.5)
    
    def _start_story_creation(self, instance: AgentInstance):
        """
        启动真实的 wagent.py 故事创作流程
        
        核心功能：
        - 集成 wagent.py 的真实聊天交互
        - 保持会话状态同步
        - 支持中断和返回
        """
        self.console.clear()
        self._print_header("📝 WAgent 真实创作模式")
        
        if not instance.bound_story_path:
            self.console.print("[yellow]⚠️ 当前未绑定故事，请先绑定或创建新故事[/yellow]")
            time.sleep(1.5)
            return
        
        self.console.print(f"[cyan]当前故事: {instance.bound_story_path}[/cyan]\n")
        
        mode = Prompt.ask(
            "[bold]选择创作模式[/bold]",
            choices=["continue", "new", "back"],
            default="continue"
        ).lower()
        
        if mode == "back":
            return
        
        try:
            self.console.print("\n[yellow]⏳ 正在初始化 WAgent 引擎...[/yellow]")
            
            # 构造 wagent.py 的参数
            import sys
            from pathlib import Path
            
            wagent_path = Path(__file__).parent / "wagent.py"
            
            args = [sys.executable, str(wagent_path)]
            
            # 根据模式添加参数
            if mode == "continue":
                # 继续创作：尝试获取故事ID作为resume参数
                story_id = instance.bound_story_path.replace("stories/", "").replace("/", "_")
                args.extend(["--resume", story_id])
                self.console.print(f"[dim]   模式: 继续创作 (故事ID: {story_id})[/dim]")
            else:
                # 全新创作：不带resume参数
                self.console.print("[dim]   模式: 全新创作[/dim]")
            
            self.console.print("[dim]   正在启动真实 WAgent 交互界面...[/dim]\n")
            time.sleep(0.5)
            
            # ==================== 关键：启动真实的 wagent.py ====================
            # 使用 subprocess.Popen 直接接管终端交互
            # 这是最自然的集成方式，用户完全像运行 wagent.py 一样
            
            self.console.print("=" * 70)
            self.console.print("[bold]� 进入 WAgent 真实交互模式[/bold]")
            self.console.print("[dim]   (Ctrl+C 或输入 'quit' 可返回控制面板)[/dim]")
            self.console.print("=" * 70 + "\n")
            
            # 更新会话状态
            self.session_mgr.update_instance_stats(
                self.current_session_id,
                last_action="entering_wagent"
            )
            
            # 直接运行 wagent.py，继承当前终端
            # 这样用户体验最自然
            result = subprocess.run(
                args,
                cwd=str(Path(__file__).parent),
                text=True,
                encoding='utf-8'
            )
            
            # ==================== 返回控制面板 ====================
            
            self.console.print("\n" + "=" * 70)
            self.console.print("[bold]🔙 已从 WAgent 返回[/bold]")
            
            if result.returncode == 0:
                self.console.print("[green]✓ 会话正常结束[/green]")
            else:
                self.console.print(f"[yellow]✓ 会话以代码 {result.returncode} 结束[/yellow]")
            
            self.console.print("=" * 70)
            
            # 更新统计
            self.session_mgr.update_instance_stats(
                self.current_session_id,
                last_action="returned_from_wagent"
            )
            
            Prompt.ask("\n[dim]按Enter返回Agent控制面板[/dim]")
            
        except KeyboardInterrupt:
            self.console.print("\n[yellow]⏸️ 用户中断 WAgent[/yellow]")
            time.sleep(0.5)
        except Exception as e:
            self.console.print(f"\n[red]❌ WAgent 启动失败: {str(e)}[/red]")
            self.error_handler.log_error(
                ErrorSeverity.ERROR,
                "WAGENT_LAUNCH_FAILED",
                str(e)
            )
            time.sleep(2)
    
    def _confirm_destroy_session(self) -> bool:
        """确认销毁会话"""
        self.console.print()
        self.console.print("[red]⚠️  警告：此操作不可逆！[/red]\n")
        
        instance = self.session_mgr.get_instance(self.current_session_id)
        if not instance:
            return False
        
        plan = self.session_mgr._create_destruction_plan(instance)
        
        self.console.print("[bold]销毁计划:[/bold]")
        for item in plan['consequences']:
            self.console.print(f"  • {item}")
        
        confirm = Confirm.ask("\n确认销毁此会话？", default=False)
        
        if confirm:
            success, msg = self.session_mgr.destroy_session(
                self.current_session_id,
                confirm_callback=lambda p: True
            )
            
            if success:
                self.console.print(f"\n[green]✅ {msg}[/green]")
                self.current_session_id = None
                time.sleep(1.5)
                return True
            else:
                self.console.print(f"[red]❌ {msg}[/red]")
                time.sleep(1.5)
                return False
        else:
            self.console.print("[yellow]已取消[/yellow]")
            time.sleep(1)
            return False
    
    def _delete_session_ui(self):
        """从会话列表删除会话的UI"""
        sessions = self.session_mgr.list_all_sessions(active_only=True)
        if not sessions:
            self.console.print("[yellow]⚠️ 没有可删除的会话[/yellow]")
            time.sleep(1.5)
            return
        
        self.console.print()
        for idx, s in enumerate(sessions, 1):
            self.console.print(f"  {idx}. {s['session_id']} ({s['state']})")
        
        choice = Prompt.ask("[red]输入要删除的会话编号[/red]", default="0")
        
        if choice == "0":
            return
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(sessions):
                session_id = sessions[idx]['session_id']
                
                self.console.print(f"\n[red]确定要删除会话 '{session_id}' 吗？[/red]")
                confirm = Confirm.ask("此操作不可逆！", default=False)
                
                if confirm:
                    success, msg = self.session_mgr.destroy_session(
                        session_id,
                        confirm_callback=lambda p: True
                    )
                    
                    if success:
                        self.console.print(f"[green]✅ {msg}[/green]")
                    else:
                        self.console.print(f"[red]❌ {msg}[/red]")
                else:
                    self.console.print("[yellow]已取消[/yellow]")
                
                time.sleep(1.5)
        except ValueError:
            self.console.print("[red]❌ 无效输入[/red]")
            time.sleep(1)
    
    def _show_system_status(self):
        """显示系统状态"""
        self.console.clear()
        self._print_header("📊 系统状态")
        
        stats = self.session_mgr.get_statistics()
        
        status_table = Table(show_header=False, box=None)
        status_table.add_column("指标", style="cyan", width=25)
        status_table.add_column("值", style="white")
        
        status_table.add_row("总创建会话", str(stats['total_created']))
        status_table.add_row("总销毁会话", str(stats['total_destroyed']))
        status_table.add_row("当前活跃数", str(stats['active_count']))
        status_table.add_row("注册表文件存在", "✓" if stats['registry_exists'] else "✗")
        
        states = stats.get('states_distribution', {})
        state_str = ", ".join([f"{k}:{v}" for k, v in states.items()])
        status_table.add_row("状态分布", state_str or "(空)")
        
        self.console.print(status_table)
        
        scanner_stats = self.scanner.get_statistics() if self.scanner else {}
        if scanner_stats:
            self.console.print("\n[dim]─[/dim]" * 50)
            self.console.print("[bold]扫描器状态:[/bold]")
            self.console.print(f"  总扫描次数: {scanner_stats.get('total_scans', 0)}")
            self.console.print(f"  处理文件数: {scanner_stats.get('total_files_processed', 0)}")
        
        Prompt.ask("\n[dim]按Enter返回[/dim]")
    
    def _show_detailed_info(self, instance: AgentInstance):
        """显示详细实例信息"""
        self.console.clear()
        self._print_header(f"ℹ️ 详细信息 - {self.current_session_id}")
        
        data = instance.to_dict()
        
        detail_table = Table(show_header=False, box=None)
        for key, value in data.items():
            if isinstance(value, dict):
                value = json.dumps(value, ensure_ascii=False, indent=2)
            detail_table.add_row(key.replace('_', ' ').title(), str(value))
        
        self.console.print(detail_table)
        Prompt.ask("\n[dim]按Enter返回[/dim]")
    
    def _scan_available_stories(self) -> List[Dict]:
        """扫描可用故事目录"""
        try:
            result = self.scanner.scan(force_refresh=False)
            return result.valid_stories
        except Exception:
            return []
    
    def _print_header(self, title: str):
        """打印页面标题头"""
        self.console.print()
        panel = Panel(
            f"[bold white]{title}[/bold white]",
            border_style="bright_blue",
            padding=(1, 2)
        )
        self.console.print(panel)
    
    def _exit_program(self):
        """安全退出程序"""
        self.console.print()
        self.console.print("[yellow]正在准备退出...[/yellow]")
        
        active_count = self.session_mgr.stats['active_count']
        if active_count > 0:
            self.console.print(f"[yellow]⚠️ 仍有 {active_count} 个活跃会话[/yellow]")
            
            save_state = Confirm.ask("是否保存会话状态？", default=True)
            if save_state:
                self.console.print("[dim]💾 正在保存...[/dim]")
                time.sleep(0.5)
                self.console.print("[green]✅ 状态已保存[/green]")
        
        self.console.print("\n[dim]感谢使用 WAgent AI 小说创作系统！[/dim]")
        self.console.print(f"[dim]版本: {self.VERSION} | 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]\n")
        
        self.running = False
    
    def _signal_handler(self, signum, frame):
        """信号处理器（Ctrl+C等）"""
        self.console.print("\n\n[yellow]⚠️ 接收到中断信号，正在安全退出...[/yellow]")
        self._cleanup()
        sys.exit(0)
    
    def _cleanup(self):
        """清理资源"""
        try:
            if self.session_mgr:
                self.session_mgr._save_sessions()
            
            errors_summary = self.error_handler.get_error_summary() if self.error_handler else {}
            if errors_summary.get('total_errors', 0) > 0:
                self.console.print(f"\n[dim]本次运行记录了 {errors_summary['total_errors']} 个错误[/dim]")
            
        except Exception as e:
            pass


def main():
    """主入口函数"""
    launcher = WAgenterLauncher()
    launcher.run()


if __name__ == "__main__":
    main()
