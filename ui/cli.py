#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WAgent V3.1 UI界面美化模块

基于错误修改.md第三优先级要求实现：
- 统一使用rich库美化所有界面
- Panel包裹重要信息
- Table展示列表数据
- 颜色区分信息类型
- 10阶段进度条
- 实时思考流显示
"""

import time
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# 尝试导入rich库，如果不可用则降级为普通输出
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
    from rich.markdown import Markdown
    from rich.live import Live
    from rich.layout import Layout
    
    RICH_AVAILABLE = True
    console = Console()
    
except ImportError:
    RICH_AVAILABLE = False
    console = None


class UIManager:
    """
    界面管理器 - V3.1可视化核心
    
    功能：
    - 进度条显示（10阶段）
    - 思考流展示（打字机效果）
    - 信息卡片生成
    - 表格和面板渲染
    """
    
    def __init__(self):
        self.current_phase = 0
        self.total_phases = 10
        self.thinking_stream: List[Dict] = []
        self._live_display = None
    
    # ============================================
    # 进度管理（10阶段）
    # ============================================
    
    PHASES = [
        ("分析用户需求", "🔍", "cyan"),
        ("调用历史上下文", "📚", "blue"),
        ("生成章节大纲", "📋", "green"),
        ("确定本章人物", "👥", "yellow"),
        ("构建人物关系", "🔗", "magenta"),
        ("设定本章主题", "💡", "red"),
        ("调整写作风格", "✍️", "white"),
        ("撰写剧情梗概", "📝", "cyan"),
        ("一致性校验", "✅", "green"),
        ("最终整理输出", "🎉", "rainbow"),
    ]
    
    def show_progress(self, phase_num: int, description: str = ""):
        """
        显示10阶段进度
        
        Args:
            phase_num: 当前阶段(1-10)
            description: 阶段描述
        """
        if not RICH_AVAILABLE:
            print(f"\n  [{phase_num}/10] {self.PHASES[phase_num-1][0]} {description}")
            return
        
        self.current_phase = phase_num
        
        # 创建进度表格
        table = Table(show_header=False, box=None, padding=(0, 2))
        
        for i, (phase_name, icon, color) in enumerate(self.PHASES, 1):
            if i < phase_num:
                status = f"[{color}]✓[/] {icon} {phase_name}"
            elif i == phase_num:
                status = f"[{color}]►[/] {icon} {phase_name}"
                if description:
                    status += f" [dim]{description}[/]"
            else:
                status = f"  ○ {icon} {phase_name}"
            
            table.add_row(status)
        
        # 显示进度百分比
        progress_pct = int((phase_num / self.total_phases) * 100)
        
        panel_content = f"[bold]AI生成进度[/]\n\n"
        panel_content += f"总进度: [cyan]{progress_pct}%[/]\n\n"
        panel_content += str(table)
        
        panel = Panel(
            panel_content,
            title="[bold blue]🎬 创作过程监控",
            border_style="blue",
            padding=(1, 2)
        )
        
        console.print(panel)
    
    def show_progress_bar(self, current: int, total: int = 100,
                          description: str = ""):
        """显示简单的进度条"""
        if RICH_AVAILABLE:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(bar_width=40),
                TextColumn("{task.completed}/{task.total}"),
                console=console
            ) as progress:
                task = progress.add_task(description or "处理中...",
                                       total=total,
                                       completed=current)
                
                while current < total:
                    current += 1
                    progress.update(task, completed=current)
                    time.sleep(0.02)
        else:
            pct = int((current / total) * 100) if total > 0 else 100
            bar_len = 40
            filled = int(bar_len * current / total)
            bar = '█' * filled + '░' * (bar_len - filled)
            print(f"\r  [{bar}] {pct}% ({current}/{total})", end="")
    
    # ============================================
    # 思考流显示
    # ============================================
    
    def add_thinking(self, content: str, thinking_type: str = "general"):
        """添加思考内容到流中"""
        entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "content": content,
            "type": thinking_type
        }
        self.thinking_stream.append(entry)
        
        if RICH_AVAILABLE:
            type_colors = {
                "analysis": "cyan",
                "memory_call": "blue",
                "character": "green",
                "outline": "yellow",
                "research": "magenta",
                "general": "white"
            }
            color = type_colors.get(thinking_type, "white")
            
            console.print(f"  [[{color}]💭{entry['timestamp']}[/]] {content}")
        else:
            print(f"  [{entry['timestamp']}] 💭 {content}")
    
    def show_thinking_stream(self):
        """显示完整的思考流"""
        if not self.thinking_stream:
            return
        
        if RICH_AVAILABLE:
            table = Table(show_header=True)
            table.add_column("时间", style="dim")
            table.add_column("类型", style="cyan")
            table.add_column("内容")
            
            for entry in self.thinking_stream[-20:]:  # 只显示最近20条
                table.add_row(
                    entry["timestamp"],
                    entry["type"],
                    entry["content"][:80]
                )
            
            console.print(table)
        else:
            print("\n  === 思考记录 ===")
            for entry in self.thinking_stream[-10:]:
                print(f"  [{entry['timestamp']}] {entry['content'][:60]}")
    
    # ============================================
    # 信息卡片显示（6项信息）
    # ============================================
    
    def show_info_card(self, data: Dict, chapter_num: int = None):
        """
        显示完整的信息卡片（6项核心信息）
        
        Args:
            data: 包含标题、人物、主题、大纲、字数等信息的字典
            chapter_num: 章节号（可选）
        """
        if not RICH_AVAILABLE:
            print("\n  === 章节信息 ===")
            print(f"  标题: {data.get('chapter_title', '未命名')}")
            print(f"  主题: {data.get('theme', '')}")
            print(f"  字数: {data.get('word_count', 0)}")
            return
        
        card_content = ""
        
        # 标题
        title = data.get('chapter_title', data.get('overall_title', '未命名'))
        card_content += f"[bold cyan]{title}[/]\n\n"
        
        # 人物列表
        characters = data.get('characters', data.get('character_relations', []))
        if characters:
            card_content += "[bold]主要角色:[/]\n"
            for char in characters[:5]:
                name = char.get('name', char.get('name', '未知'))
                role = char.get('role', char.get('role', ''))
                card_content += f"  • [green]{name}[/] - {role}\n"
            card_content += "\n"
        
        # 主题
        theme = data.get('theme', data.get('core_theme', ''))
        if theme:
            card_content += f"[bold]主题:[/] [yellow]{theme}[/]\n\n"
        
        # 大纲/摘要
        outline = data.get('outline', data.get('summary', data.get('detailed_outline', '')))
        if outline:
            card_content += "[bold]内容概要:[/]\n"
            card_content += f"[dim]{outline[:200]}[/]\n\n"
        
        # 字数
        word_count = data.get('word_count', data.get('word_count_target', 0))
        if word_count:
            card_content += f"[bold]字数:[/] [cyan]{word_count}[/] 字\n"
        
        # 章节号
        if chapter_num:
            card_content += f"[bold]章节:[/] 第[red]{chapter_num}[/]章"
        
        panel = Panel(
            card_content,
            title=f"[bold green]📖 章节信息卡{' (第' + str(chapter_num) + '章)' if chapter_num else ''}",
            border_style="green",
            width=60
        )
        
        console.print("\n")
        console.print(panel)
    
    # ============================================
    # 列表展示
    # ============================================
    
    def show_session_list(self, sessions: List[Dict]):
        """显示会话列表"""
        if not sessions:
            if RICH_AVAILABLE:
                console.print("[yellow]暂无会话[/]")
            else:
                print("  暂无会话")
            return
        
        if RICH_AVAILABLE:
            table = Table(title="会话列表")
            table.add_column("#", style="cyan", justify="right")
            table.add_column("会话ID", style="dim")
            table.add_column("故事名称", style="green")
            table.add_column("章节数", justify="center")
            table.add_column("状态", style="yellow")
            table.add_column("更新时间", style="dim")
            
            for i, session in enumerate(sessions, 1):
                table.add_row(
                    str(i),
                    session.get('session_id', '')[:12],
                    session.get('story_name', ''),
                    str(session.get('chapter_count', 0)),
                    session.get('status', 'active'),
                    session.get('updated_at', '')[:16].replace('T', ' ')
                )
            
            console.print(table)
        else:
            print("\n  === 会话列表 ===")
            for i, session in enumerate(sessions, 1):
                print(f"  {i}. {session.get('story_name', '')} "
                      f"({session.get('chapter_count', 0)}章)")
    
    # ============================================
    # 状态消息
    # ============================================
    
    def success(self, message: str):
        """显示成功消息"""
        if RICH_AVAILABLE:
            console.print(f"[green]✓[/] {message}")
        else:
            print(f"  ✓ {message}")
    
    def error(self, message: str):
        """显示错误消息"""
        if RICH_AVAILABLE:
            console.print(f"[red]✗[/] {message}")
        else:
            print(f"  ✗ {message}")
    
    def warning(self, message: str):
        """显示警告消息"""
        if RICH_AVAILABLE:
            console.print(f"[yellow]⚠[/] {message}")
        else:
            print(f"  ⚠ {message}")
    
    def info(self, message: str):
        """显示一般信息"""
        if RICH_AVAILABLE:
            console.print(f"[blue]ℹ[/] {message}")
        else:
            print(f"  ℹ {message}")
    
    # ============================================
    # Banner和框架
    # ============================================
    
    def show_banner(self, version: str = "V3.1"):
        """显示系统Banner"""
        banner_content = f"""
[bold blue]
╔══════════════════════════════════════╗
║                                      ║
║   WAgent 多AI协同智能写作系统       ║
║          版本: {version:<18} ║
║                                      ║
╚══════════════════════════════════════╝
[/]
"""
        if RICH_AVAILABLE:
            console.print(Markdown(banner_content))
        else:
            print(f"\n{'='*50}")
            print(f"  WAgent 多AI协同智能写作系统 {version}")
            print(f"{'='*50}")
    
    def show_main_menu(self):
        """显示主菜单"""
        menu_items = [
            ("1", "选择已有会话"),
            ("2", "新建会话"),
            ("3", "删除会话"),
            ("4", "查看故事路径"),
            ("5", "搜索会话"),
            ("6", "退出系统"),
        ]
        
        if RICH_AVAILABLE:
            table = Table(title="主菜单", show_header=False, padding=(0, 4))
            table.add_column("选项", style="cyan", justify="center")
            table.add_column("功能", style="green")
            
            for num, desc in menu_items:
                table.add_row(num, desc)
            
            console.print(table)
        else:
            print("\n  === 主菜单 ===")
            for num, desc in menu_items:
                print(f"  {num}. {desc}")


def create_ui_manager() -> UIManager:
    """工厂函数：创建UI管理器实例"""
    return UIManager()
