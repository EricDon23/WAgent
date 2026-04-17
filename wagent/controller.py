#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WAgent主控制器模块 (v5.2 - 约束保障与闭环控制版)

功能：
1. 多角色AI协同工作机制（导演→研究员→作家）
2. 章节生成完整闭环（用户输入→导演验证→资料搜索→作家创作→用户确认）
3. 上下文管理系统（查看/补充/修改/筛选/整合）
4. 约束保障机制（持续监控+审计跟踪+回滚查看）
5. 自动保存与故事树节点持久化

v5.2 更新：
- 集成ConstraintManager约束保障系统
- 实现严格的章节生成闭环控制
- 增强上下文管理与修改操作审计
- 优化用户体验与状态反馈
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.markdown import Markdown
    RICH_AVAILABLE = True
except ImportError:
    Console = Panel = Table = Markdown = None
    RICH_AVAILABLE = False

from .config import (
    SystemState, UserCommand, AsyncConfig, ConstraintConfig, FeatureFlags
)
from .normalizer import TextNormalizer
from .display import RealtimeDisplay
from .logger import ThinkingLogger
from .cache import AsyncCacheManager
from .engines import DirectorAI, ResearcherAI, WriterAI
from .utils.interactive import InteractivePrompt, confirm
from .utils.archiver import ZipArchiver
from .story_session import StorySessionManager, StoryNode, ChapterRecord, get_session_manager
from .constraint_manager import (
    ConstraintManager, ConstraintType, AuditAction,
    create_constraint_manager, UserConstraint
)


class WAgent:
    """
    WAgent v5.2 - 约束保障故事创作系统主控制器
    
    核心特性：
    - 完整闭环控制：用户→导演→研究员→作家→确认→保存
    - 约束保障：实时监控内容生成，确保符合用户初始设定
    - 审计跟踪：记录所有关键变更，支持回滚查看
    - 上下文管理：支持大纲/资料的查看、补充、修改、筛选
    """
    
    def __init__(self, flags: FeatureFlags = None):
        self.flags = flags or FeatureFlags.from_env()
        
        self.display = RealtimeDisplay(self.flags)
        self.logger = ThinkingLogger()
        self.cache = AsyncCacheManager()
        
        self.normalizer = TextNormalizer(self.flags)
        self.prompt_tool = InteractivePrompt(
            case_insensitive=self.flags.case_insensitive_commands,
            max_retries=self.flags.max_retry_attempts
        )
        
        self.config = AsyncConfig()
        self.director: Optional[DirectorAI] = None
        self.researcher: Optional[ResearcherAI] = None
        self.writer: Optional[WriterAI] = None
        
        # 创作状态管理
        self.story_setting: Optional[Dict] = None
        self.knowledge_base: Optional[Dict] = None
        self.chapters: List[Dict] = []
        self.story_id: str = f"story_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.current_round: int = 0
        self.is_finished: bool = False
        
        # 故事会话管理（树节点系统）
        self.session_manager: StorySessionManager = None
        self.story_node: Optional[StoryNode] = None
        
        # ★★★ 约束保障管理器 ★★★
        self.constraint_mgr: Optional[ConstraintManager] = None
        
        # 输出目录
        self.output_dir = Path("stories") / self.story_id
        self.info_dir = None      # 信息文档目录
        self.novel_dir = None     # 小说文档目录
        
        self.console = Console() if RICH_AVAILABLE else Console
    
    async def initialize(self, resume_story_id: str = None):
        """初始化所有组件"""
        self.display.update(SystemState.INITIALIZING,"初始化...",5,"加载组件...")
        await asyncio.sleep(0.3)
        
        await self.cache.init()
        
        self.director = DirectorAI(self.config,self.logger,self.cache)
        self.researcher = ResearcherAI(self.config,self.logger,self.cache)
        self.writer = WriterAI(self.config,self.logger,self.cache)
        
        # 初始化故事会话管理器
        self.session_manager = StorySessionManager(base_dir="stories")
        
        # 如果指定了恢复的故事ID，则加载
        if resume_story_id:
            self.story_node = self.session_manager.load_story(resume_story_id)
            if self.story_node:
                self.story_id = self.story_node.story_id
                self.story_setting = self.story_node.setting
                self.knowledge_base = self.story_node.knowledge_base
                
                # 恢复章节列表
                self.chapters = []
                for ch in self.story_node.get_all_chapters():
                    self.chapters.append({
                        'data': {
                            'chapter_num': ch.chapter_num,
                            'content': ch.content,
                            'word_count': ch.word_count,
                            'constraint_check': {'passed': True, 'message': f"{ch.status}状态"}
                        }
                    })
                
                self.current_round = self.story_node.session_count
                self.output_dir = Path("stories") / self.story_id
                (self.output_dir).mkdir(parents=True, exist_ok=True)
                (self.output_dir / "info").mkdir(exist_ok=True)
                (self.output_dir / "novel").mkdir(exist_ok=True)
                
                # ★★★ 恢复约束管理器 ★★★
                self.constraint_mgr = create_constraint_manager(str(self.output_dir))
                
                self.display.update(SystemState.READY,"就绪",100,f"已恢复: {self.story_node.title}")
                self.console.print(f"[green]✅ 已恢复故事: {self.story_node.title}[/green]")
                self.console.print(f"[dim]   📚 章节: {len(self.chapters)} | 字数: {self.story_node.total_words}[/dim]")
                return
        
        # 创建输出目录结构（新故事）
        self._setup_output_dirs()
        
        # ★★★ 初始化约束管理器 ★★★
        self.constraint_mgr = create_constraint_manager(str(self.output_dir))
        
        # 创建新故事节点
        self.story_node = self.session_manager.create_story(
            story_id=self.story_id,
            title="",
            prompt=""
        )
        
        self.display.update(SystemState.READY,"就绪",100,"系统准备完毕")
        
        self.console.print("[green]✅ WAgent v5.2 初始化完成[/green]")
        self.console.print(f"[dim]   📁 输出目录: {self.output_dir}[/dim]")
    
    def _setup_output_dirs(self):
        """创建输出目录结构"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 信息文档目录（存放设定、研究资料等）
        self.info_dir = self.output_dir / "info"
        self.info_dir.mkdir(exist_ok=True)
        
        # 小说文档目录（存放章节内容）
        self.novel_dir = self.output_dir / "novel"
        self.novel_dir.mkdir(exist_ok=True)
        
        (self.output_dir / "archive").mkdir(exist_ok=True)
    
    async def _save_info_document(self, doc_type: str, data: Dict, 
                                   filename: str = None) -> str:
        """保存信息文档（设定/研究/日志等）"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{doc_type}_{timestamp}.json"
        
        filepath = self.info_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        
        self.console.print(f"[dim]   💾 已保存: {filename}[/dim]")
        return str(filepath)
    
    async def _save_novel_chapter(self, chapter_data: Dict, 
                                    chapter_num: int) -> str:
        """保存小说章节文档"""
        content = chapter_data.get('data', {}).get('content', '')
        word_count = len(content)
        
        branch = f"branch_{self.current_round:02d}"
        filename = f"{self.story_id}--{branch}-chap_{chapter_num:02d}.md"
        filepath = self.novel_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            story_name = self.story_setting.get('story_name', '未命名故事')
            f.write(f"# {story_name}\n\n")
            f.write(f"> 第{chapter_num}章 | {word_count}字 | 生成于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")
            f.write(content)
            
            if content and not content.endswith('\n'):
                f.write('\n')
        
        self.console.print(f"[dim]   📝 已保存: 第{chapter_num}章 ({word_count}字)[/dim]")
        return str(filepath)
    
    async def _save_full_novel(self) -> str:
        """合并保存完整小说"""
        novel_path = self.novel_dir / f"{self.story_id}_full.md"
        
        with open(novel_path, 'w', encoding='utf-8') as f:
            story_name = self.story_setting.get('story_name', '未命名故事')
            
            f.write(f"# {story_name}\n\n")
            f.write(f"> **WAgent 自动生成作品**\n")
            f.write(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"> 总章节数: {len(self.chapters)}\n\n")
            
            total_words = 0
            for i, ch in enumerate(self.chapters, 1):
                data = ch.get('data', {})
                content = data.get('content', '')
                wc = len(content)
                total_words += wc
                
                f.write(f"---\n\n## 第{i}章 ({wc}字)\n\n")
                f.write(content)
                f.write('\n\n')
            
            f.write(f"\n---\n\n*全文共计 {total_words} 字*\n")
        
        return str(novel_path)
    
    def show_banner(self):
        """显示欢迎横幅"""
        banner = f"""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║     🚀 WAgent v5.2 - 约束保障故事创作系统                     ║
║                                                               ║
║     ⚡ 闭环控制 | 🔒 约束保障 | 📋 审计跟踪                  ║
║     ✨ 大纲确认 | 💾 实时保存 | ↩️ 回滚支持                 ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝

💡 输入您的创意开始创作（或输入 help 查看命令列表）
"""
        self.console.print(banner)
    
    def show_help(self):
        """显示帮助信息"""
        help_text = """
┌─────────────────────────────────────────────────────────────┐
│                     可用命令                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   continue / c / 回车    → 继续创作下一章                  │
│   modify / m             → 修改当前章节                      │
│   regenerate / r         → 重新生成当前章节                  │
│   context / ct           → 查看和管理上下文                  │
│   constraints / cs       → 查看当前约束条件                  │
│   audit / ad             → 查看审计日志                      │
│   finish / f             → 完结小说并打包                   │
│   status / s             → 查看当前状态                      │
│   help / h               → 显示此帮助                        │
│   quit / q               → 退出程序                          │
│                                                             │
│   其他输入                 → 作为创作指令传递给AI           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
"""
        self.console.print(help_text)
    
    def show_status(self):
        """显示当前状态（增强版）"""
        table = Table(show_header=True,title="📊 当前状态",border_style="cyan")
        table.add_column("项目",style="bold cyan")
        table.add_column("值",style="white")
        
        story_name = self.story_setting.get('story_name','未设置') if self.story_setting else '未设置'
        table.add_row("故事ID",self.story_id)
        table.add_row("故事标题",story_name)
        table.add_row("当前轮次",str(self.current_round))
        table.add_row("已生成章节数",str(len(self.chapters)))
        total_words = sum(c['data']['word_count'] for c in self.chapters if c.get('data'))
        table.add_row("总字数",f"{total_words}字")
        table.add_row("知识库","已生成" if self.knowledge_base else "未生成")
        table.add_row("约束条件",f"{len(self.constraint_mgr.constraints) if self.constraint_mgr else 0}项")
        table.add_row("审计记录",f"{len(self.constraint_mgr.audit_records) if self.constraint_mgr else 0}条")
        table.add_row("输出目录",str(self.output_dir))
        table.add_row("状态","已完结" if self.is_finished else "进行中")
        
        self.console.print(table)
    
    def show_setting(self, setting: Dict):
        """显示故事设定"""
        self.console.print("\n"+"="*60)
        self.console.print(f"[bold cyan]📖 故事设定[/bold cyan]")
        self.console.print("="*60)
        
        t = Table(show_header=False)
        t.add_column("字段",style="cyan",width=14)
        t.add_column("内容")
        t.add_row("📚 标题",setting.get('story_name',''))
        t.add_row("📄 梗概",setting.get('story_summary',''))
        t.add_row("📖 简介",(setting.get('story_intro','') or '')[:200]+"...")
        t.add_row("🎯 主题",setting.get('theme',''))
        t.add_row("⚙️ 约束",setting.get('constraints',''))
        self.console.print(t)
        
        self.console.print("\n[bold]👥 角色:[/bold]")
        for i,ch in enumerate(setting.get('characters',[]),1):
            self.console.print(f"  {i}. {ch.get('name','')} - {ch.get('role','')}")
        
        self.console.print(f"\n[bold]🔬 研究:[/bold]")
        for n in setting.get('research_needs',[]):
            self.console.print(f"  • {n}")
        self.console.print()
    
    def show_chapter(self, chapter_result: Dict):
        """显示章节（带约束检查结果）"""
        data = chapter_result['data']
        content = data['content']
        
        self.console.print("\n"+"="*60)
        self.console.print(f"[bold magenta]📝 第{data['chapter_num']}章[/bold magenta] "
                     f"({data['word_count']}字)")
        self.console.print("="*60)
        
        preview = content[:500] if len(content)>500 else content
        self.console.print(Markdown(preview))
        
        if len(content)>500:
            self.console.print(f"\n[dim]... 共{len(content)}字[/dim]")
        
        check = data.get('constraint_check',{})
        color = "green" if check.get('passed') else "red"
        msg_text = check.get('message', '')
        self.console.print(f"\n[{color}]⚖️ {msg_text}[/{color}]")
        self.console.print()
    
    def parse_command(self, user_input: str) -> UserCommand:
        """解析用户命令"""
        normalized = self.normalizer.normalize_command(user_input)
        
        cmd_map = {
            'continue':UserCommand.CONTINUE,'c':UserCommand.CONTINUE,
            'next':UserCommand.CONTINUE,'n':UserCommand.CONTINUE,
            'go':UserCommand.CONTINUE,
            '':UserCommand.CONTINUE,
            'modify':UserCommand.MODIFY,'m':UserCommand.MODIFY,
            'edit':UserCommand.MODIFY,'e':UserCommand.MODIFY,
            'regenerate':UserCommand.REGENERATE,'r':UserCommand.REGENERATE,
            'redo':UserCommand.REGENERATE,
            'finish':UserCommand.FINISH,'f':UserCommand.FINISH,
            'end':UserCommand.FINISH,
            'done':UserCommand.FINISH,
            'save':UserCommand.FINISH,
            'status':UserCommand.STATUS,'s':UserCommand.STATUS,
            'context':UserCommand.CONTEXT,'ct':UserCommand.CONTEXT,
            'constraints':UserCommand.CONSTRAINTS,'cs':UserCommand.CONSTRAINTS,
            'audit':UserCommand.AUDIT,'ad':UserCommand.AUDIT,
            'help':UserCommand.HELP,'h':UserCommand.HELP,
            '?':UserCommand.HELP,
            'quit':UserCommand.QUIT,'q':UserCommand.QUIT,
            'exit':UserCommand.QUIT,
        }
        
        return cmd_map.get(normalized, UserCommand.CONTINUE)
    
    # ========== ★★★ 需求#1: 多角色AI协同机制增强 ★★★
    
    def _extract_constraints_from_setting(self, setting: Dict) -> List[Tuple[ConstraintType, str, Any]]:
        """
        从故事设定中自动提取约束条件
        
        Returns:
            [(约束类型, 描述, 值), ...]
        """
        constraints = []
        
        # 1. 字数约束
        word_count_range = setting.get('word_count_range', {})
        if word_count_range:
            constraints.append((
                ConstraintType.WORD_COUNT,
                f"每章字数范围: {word_count_range.get('min',0)}-{word_count_range.get('max','无限制')}字",
                {'min': word_count_range.get('min', 0), 'max': word_count_range.get('max', float('inf'))}
            ))
        
        # 2. 风格约束
        style = setting.get('style', '')
        if style:
            style_keywords = [s.strip() for s in style.split(',')]
            constraints.append((
                ConstraintType.STYLE,
                f"写作风格: {style}",
                style_keywords
            ))
        
        # 3. 内容约束（禁止词/必须包含的元素）
        content_rules = setting.get('content_rules', {})
        if content_rules:
            constraints.append((
                ConstraintType.CONTENT,
                "内容规则",
                content_rules
            ))
        
        # 4. 类型/题材约束
        genre = setting.get('genre', '')
        if genre:
            constraints.append((
                ConstraintType.WORLD_BUILDING,
                f"世界观类型: {genre}",
                genre
            ))
        
        return constraints
    
    async def run_initialization_phase(self, user_input: str) -> bool:
        """
        运行初始化阶段（导演 + 研究员）- 完整闭环版本
        
        流程（需求#2）：
        1. 导演AI接收用户输入 → 执行约束判断与验证
        2. 生成创作大纲 → 显示给用户
        3. 【暂停】等待用户确认（Y/N循环修改）
        4. 用户确认后 → 自动触发资料搜索模块
        5. 研究员AI收集资料
        6. 验证研究资料是否符合约束
        7. 自动保存设定和研究文档
        """
        
        # ========== 阶段1: 导演AI（约束验证）==========
        self.console.print("\n─"*60)
        self.console.print("[bold cyan]🎬 阶段1/3: 导演AI - 接收与验证[/bold cyan]")
        self.console.print("[dim]正在分析您的创意并执行约束检查...[/dim]")
        self.console.print("─"*60+"\n")
        
        # 导演AI生成大纲
        self.story_setting = await self.director.generate(user_input, self.display)
        
        # ★★★ 从设定中提取并注册约束条件 ★★★
        extracted_constraints = self._extract_constraints_from_setting(self.story_setting)
        for ctype, desc, value in extracted_constraints:
            self.constraint_mgr.add_constraint(ctype, desc, value)
        
        self.console.print(f"[dim]   🔒 已注册 {len(extracted_constraints)} 项约束条件[/dim]")
        
        # ★★★ 创建设定快照（用于回滚）★
        setting_snapshot = self.constraint_mgr.create_snapshot(
            "setting",
            self.story_setting.copy(),
            description="初始故事设定"
        )
        self.console.print(f"[dim]   📸 已创建设定快照: {setting_snapshot.snapshot_id}[/dim]")
        
        # ★★★ 唯一的Y/N确认点：大纲确认 ★★★
        while True:
            self.show_setting(self.story_setting)
            
            # 显示当前约束条件摘要
            self._show_constraints_summary()
            
            is_confirmed = self.prompt_tool.confirm(
                "✅ 是否满意此设定？(确认后将进入资料搜索阶段)",
                default=True,
                hint="[Y/n]"
            )
            
            if is_confirmed:
                break
            
            mod_input = self.prompt_tool.input_text(
                "✏️ 请输入修改意见:",
                allow_empty=False,
                default=""
            )
            
            if mod_input and mod_input.strip():
                before_state = self.story_setting.copy()
                
                self.story_setting = await self.director.refine(
                    self.story_setting, 
                    mod_input.strip(),
                    self.display
                )
                
                # ★★★ 记录修改审计 ★★★
                self.constraint_mgr.audit_action(
                    action=AuditAction.MODIFY,
                    target_type="setting",
                    target_id=self.story_id,
                    before=before_state,
                    after=self.story_setting.copy(),
                    user_input=mod_input.strip(),
                    details=f"用户修改大纲: {mod_input.strip()[:50]}"
                )
        
        # ★★★ 用户确认后的审计记录 ★★★
        self.constraint_mgr.audit_action(
            action=AuditAction.CONFIRM,
            target_type="setting",
            target_id=self.story_id,
            details="用户确认故事设定"
        )
        
        # ★★★ 自动保存：故事设定文档 ★★★
        self.console.print("\n[dim]💾 正在保存故事设定...[/dim]")
        setting_file = await self._save_info_document(
            "story_setting",
            self.story_setting,
            "01_story_setting.json"
        )
        
        # ★★★ 更新故事节点（设定阶段） ★★★
        if self.story_node:
            self.story_node.title = self.story_setting.get('story_name', '')
            self.story_node.genre = self.story_setting.get('genre', '')
            self.story_node.setting = self.story_setting
            self.story_node.original_prompt = user_input
            self.session_manager.save_story(self.story_node)
            self.console.print(f"[dim]   🌳 故事树节点已更新: {self.story_node.title}[/dim]")
        
        # ========== 阶段2: 研究员AI（自动触发）==========
        self.console.print("\n─"*60)
        self.console.print("[bold yellow]🔍 阶段2/3: 研究员AI - 资料检索[/bold yellow]")
        self.console.print("[dim](导演确认后自动触发)[/dim]")
        self.console.print("─"*60+"\n")
        
        self.knowledge_base = await self.researcher.generate(
            needs=self.story_setting.get('research_needs',[]),
            title=self.story_setting.get('story_name',''),
            genre=self.story_setting.get('genre',''),
            display=self.display
        )
        
        # ★★★ 验证研究资料是否符合约束 ★★★
        research_content = json.dumps(self.knowledge_base, ensure_ascii=False)
        is_valid, violations = self.constraint_mgr.validate_content(research_content, 0)
        
        if not is_valid and violations:
            self.console.print(f"\n[yellow]⚠️ 发现 {len(violations)} 项潜在问题:[/yellow]")
            for v in violations[:3]:
                sev_icon = {'critical':'❌','major':'⚠️','minor':'ℹ️'}.get(v.severity,'•')
                self.console.print(f"   {sev_icon} {v.constraint_description}: {v.expected_value}")
        else:
            self.console.print(f"\n[green]✅ 研究资料通过约束检查[/green]")
        
        # ★★★ 创建研究资料快照 ★★★
        kb_snapshot = self.constraint_mgr.create_snapshot(
            "knowledge",
            self.knowledge_base.copy() if isinstance(self.knowledge_base, dict) else {},
            description="研究资料"
        )
        
        # ★★★ 自动保存：研究资料文档 ★★★
        self.console.print("\n[dim]💾 正在保存研究资料...[/dim]")
        research_file = await self._save_info_document(
            "knowledge_base",
            self.knowledge_base,
            "02_knowledge_base.json"
        )
        
        # ★★★ 更新故事节点（研究阶段） ★★★
        if self.story_node:
            self.story_node.knowledge_base = self.knowledge_base
            self.session_manager.save_story(self.story_node)
            self.console.print(f"[dim]   🌳 研究资料已保存到节点[/dim]")
        
        # 初始化完成汇总
        self.console.print("\n" + "="*60)
        self.console.print("[green]✅ 初始化阶段完成！[/green]")
        self.console.print("="*60)
        self.console.print(f"   故事: {self.story_setting.get('story_name','')}")
        self.console.print(f"   研究: {len(self.knowledge_base.get('key_findings',[]))}条发现")
        self.console.print(f"   约束: {len(self.constraint_mgr.constraints)}项生效中")
        self.console.print(f"[dim]   📁 设定档: {Path(setting_file).name}[/dim]")
        self.console.print(f"[dim]   📁 研究档: {Path(research_file).name}[/dim]\n")
        
        return True
    
    # ========== ★★★ 需求#2: 章节生成闭环控制 ★★★
    
    async def run_writing_phase(self, instructions: str = "") -> bool:
        """
        运行写作阶段 - 完整闭环版本
        
        流程（需求#2）：
        1. 作家AI基于大纲+资料生成完整章节
        2. 约束系统验证章节内容
        3. 显示章节内容给用户
        4. 【暂停】等待用户确认（Y/N循环修改直到满意）
        5. 用户确认后 → 自动保存章节 → 更新故事节点
        6. 进入下一章或结束
        """
        self.current_round += 1
        ch_num = len(self.chapters) + 1
        
        self.console.print("\n─"*60)
        self.console.print(f"[bold magenta]✍️ 创作: 第{ch_num}章 (第{self.current_round}轮)[/bold magenta]")
        self.console.print("[dim]作家AI正在基于大纲和资料创作...[/dim]")
        self.console.print("─"*60+"\n")
        
        prev = self.chapters[-1]['data']['content'] if self.chapters else ""
        
        # 作家AI生成章节
        chapter = await self.writer.generate(
            ch_num=ch_num,
            setting=self.story_setting,
            kb=self.knowledge_base,
            prev_chapter=prev,
            instructions=instructions,
            display=self.display
        )
        
        self.chapters.append(chapter)
        
        # ★★★ 约束验证 ★★★
        content = chapter.get('data', {}).get('content', '')
        is_valid, violations = self.constraint_mgr.validate_content(content, ch_num)
        
        if not is_valid and violations:
            chapter['data']['constraint_check'] = {
                'passed': False,
                'message': f"发现{len(violations)}项约束问题（详见constraints命令）",
                'violations': [v.to_dict() for v in violations]
            }
        else:
            chapter['data']['constraint_check'] = {
                'passed': True,
                'message': "✅ 所有约束条件均已满足"
            }
        
        # ★★★ 章节满意度确认（允许修改直到满意）★
        while True:
            self.show_chapter(chapter)
            
            # 如果有违规，额外提示
            if not chapter['data']['constraint_check'].get('passed'):
                self.console.print(f"[yellow]⚠️ 注意: 存在约束违规，建议先修改再确认[/yellow]")
            
            is_satisfied = self.prompt_tool.confirm(
                "😊 对此章满意吗？(确认后将自动保存)",
                default=None,
                hint="[Y/n]"
            )
            
            if is_satisfied:
                break
            
            mod_input = self.prompt_tool.input_text(
                "✏️ 请输入修改意见:",
                allow_empty=False
            )
            
            if mod_input and mod_input.strip():
                before_content = chapter.get('data', {}).get('content', '')[:200]
                
                chapter = await self.writer.modify(chapter, mod_input.strip(), self.display)
                self.chapters[-1] = chapter
                
                # ★★★ 重新验证修改后的内容 ★★★
                new_content = chapter.get('data', {}).get('content', '')
                is_valid, new_violations = self.constraint_mgr.validate_content(new_content, ch_num)
                
                if not is_valid and new_violations:
                    chapter['data']['constraint_check'] = {
                        'passed': False,
                        'message': f"修改后仍有{len(new_violations)}项问题"
                    }
                else:
                    chapter['data']['constraint_check'] = {
                        'passed': True,
                        'message': "✅ 修改后约束已满足"
                    }
                
                # ★★★ 记录修改审计 ★★★
                self.constraint_mgr.audit_action(
                    action=AuditAction.MODIFY,
                    target_type="chapter",
                    target_id=f"chapter_{ch_num}",
                    before={'preview': before_content},
                    after={'preview': new_content[:200]},
                    user_input=mod_input.strip(),
                    details=f"修改第{ch_num}章: {mod_input.strip()[:50]}"
                )
        
        # ★★★ 用户确认章节后的审计记录 ★★★
        self.constraint_mgr.audit_action(
            action=AuditAction.CONFIRM,
            target_type="chapter",
            target_id=f"chapter_{ch_num}",
            details=f"用户确认第{ch_num}章"
        )
        
        # ★★★ 自动保存：单章节文档 ★★★
        self.console.print("\n[dim]💾 正在保存章节...[/dim]")
        chapter_file = await self._save_novel_chapter(chapter, ch_num)
        
        # ★★★ 创建章节快照（用于回滚）★
        ch_snapshot = self.constraint_mgr.create_snapshot(
            "chapter",
            {
                'chapter_num': ch_num,
                'content': chapter.get('data', {}).get('content', ''),
                'word_count': chapter.get('data', {}).get('word_count', 0),
                'round': self.current_round
            },
            description=f"第{ch_num}章最终版"
        )
        self.console.print(f"[dim]   📸 已创建章节快照: {ch_snapshot.snapshot_id}[/dim]")
        
        # ★★★ 自动保存：更新完整小说合并文档 ★★★
        full_novel = await self._save_full_novel()
        
        # ★★★ 保存章节到故事树节点 ★★★
        if self.story_node:
            chapter_record = ChapterRecord(
                chapter_num=ch_num,
                title=f"第{ch_num}章",
                content=chapter.get('data', {}).get('content', ''),
                status="final"
            )
            self.story_node.add_chapter(chapter_record)
            self.session_manager.save_story(self.story_node)
            self.console.print(f"[dim]   🌳 章节已保存到故事节点 (总{self.story_node.total_chapters}章)[/dim]")
        
        self.console.print(f"\n[green]✅ 第{ch_num}章完成并已保存！[/green]")
        self.console.print(f"[dim]   📁 章节: {Path(chapter_file).name}[/dim]")
        self.console.print(f"[dim]   📁 全文: {Path(full_novel).name}[/dim]\n")
        
        return True
    
    # ========== ★★★ 需求#3: 上下文管理系统 ★★★
    
    def _show_constraints_summary(self):
        """显示约束条件摘要"""
        if not self.constraint_mgr or not self.constraint_mgr.constraints:
            return
        
        self.console.print("\n[bold dim]🔒 当前约束条件:[/bold dim]")
        for i, c in enumerate(self.constraint_mgr.constraints[:5], 1):
            mandatory = "★" if c.is_mandatory else "☆"
            self.console.print(f"   {i}. {mandatory} [{c.type.value}] {c.description}")
        
        if len(self.constraint_mgr.constraints) > 5:
            self.console.print(f"   ... 还有 {len(self.constraint_mgr.constraints)-5} 项")
    
    def show_context_management(self):
        """
        显示上下文管理界面（需求#3）
        
        功能：
        - 查看当前创作大纲
        - 补充/修改大纲内容
        - 管理/筛选/整合研究资料
        - 所有修改需符合"剧情合理性"原则
        """
        self.console.print("\n" + "="*60)
        self.console.print("[bold cyan]📋 上下文管理中心[/bold cyan]")
        self.console.print("="*60)
        
        while True:
            self.console.print("\n可用操作:")
            self.console.print("  1. 查看创作大纲 (outline)")
            self.console.print("  2. 修改大纲 (modify_outline)")
            self.console.print("  3. 查看研究资料 (knowledge)")
            self.console.print("  4. 筛选资料 (filter)")
            self.console.print("  5. 整合资料到创作 (integrate)")
            self.console.print("  6. 返回主菜单 (back)")
            
            choice = input("\n请选择操作: ").strip().lower()
            
            if choice in ['1', 'outline']:
                self._show_outline_view()
            
            elif choice in ['2', 'modify_outline']:
                self._handle_outline_modification()
            
            elif choice in ['3', 'knowledge']:
                self._show_knowledge_view()
            
            elif choice in ['4', 'filter']:
                self._handle_knowledge_filter()
            
            elif choice in ['5', 'integrate']:
                self._handle_knowledge_integration()
            
            elif choice in ['6', 'back', 'q', 'quit']:
                break
            
            else:
                self.console.print("[yellow]无效选择，请重试[/yellow]")
    
    def _show_outline_view(self):
        """查看当前创作大纲"""
        if not self.story_setting:
            self.console.print("[yellow]⚠️ 尚无故事设定[/yellow]")
            return
        
        self.console.print("\n"+"─"*50)
        self.console.print("[bold]📖 当前创作大纲[/bold]")
        self.console.print("─"*50)
        
        self.show_setting(self.story_setting)
        
        # 显示相关约束
        if self.constraint_mgr and self.constraint_mgr.constraints:
            self.console.print(f"\n[bold dim]关联约束: {len(self.constraint_mgr.constraints)}项[/bold dim]")
    
    def _handle_outline_modification(self):
        """
        处理大纲修改（需求#3 - 符合剧情合理性原则）
        """
        if not self.story_setting:
            self.console.print("[yellow]⚠️ 尚无故事设定可修改[/yellow]")
            return
        
        self.console.print("\n"+"─"*50)
        self.console.print("[bold]✏️ 修改创作大纲[/bold]")
        self.console.print("─"*50)
        self.console.print("[dim]注意: 修改应符合剧情合理性原则，保持风格/逻辑/价值观一致[/dim]\n")
        
        mod_input = input("请输入修改指令: ").strip()
        
        if not mod_input:
            self.console.print("[yellow]取消修改[/yellow]")
            return
        
        # 记录修改前状态
        before_state = self.story_setting.copy()
        
        # 执行修改
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            self.story_setting = loop.run_until_complete(
                self.director.refine(self.story_setting, mod_input, self.display)
            )
        finally:
            loop.close()
        
        # ★★★ 审计记录 ★★★
        self.constraint_mgr.audit_action(
            action=AuditAction.MODIFY,
            target_type="setting",
            target_id=self.story_id,
            before=before_state,
            after=self.story_setting.copy(),
            user_input=mod_input,
            details="用户通过上下文管理修改大纲"
        )
        
        # 更新快照
        self.constraint_mgr.create_snapshot(
            "setting",
            self.story_setting.copy(),
            description="大纲修改后"
        )
        
        # 保存
        if self.story_node:
            self.story_node.setting = self.story_setting
            self.session_manager.save_story(self.story_node)
        
        self.console.print("\n[green]✅ 大纲已更新[/green]")
        self.show_setting(self.story_setting)
    
    def _show_knowledge_view(self):
        """查看研究资料"""
        if not self.knowledge_base:
            self.console.print("[yellow]⚠️ 尚无研究资料[/yellow]")
            return
        
        self.console.print("\n"+"─"*50)
        self.console.print("[bold]🔍 研究资料库[/bold]")
        self.console.print("─"*50)
        
        findings = self.knowledge_base.get('key_findings', [])
        self.console.print(f"\n共 {len(findings)} 条研究发现:\n")
        
        for i, finding in enumerate(findings[:10], 1):
            title = finding.get('title', '未命名')
            summary = finding.get('summary', '')[:100]
            self.console.print(f"  {i}. {title}")
            self.console.print(f"     {summary}...")
        
        if len(findings) > 10:
            self.console.print(f"\n  ... 还有 {len(findings)-10} 条")
    
    def _handle_knowledge_filter(self):
        """
        处理资料筛选（需求#3）
        """
        if not self.knowledge_base:
            self.console.print("[yellow]⚠️ 无资料可筛选[/yellow]")
            return
        
        self.console.print("\n"+"─"*50)
        self.console.print("[bold]🔎 资料筛选[/bold]")
        self.console.print("─"*50)
        
        keyword = input("请输入筛选关键词: ").strip()
        
        if not keyword:
            self.console.print("[yellow]取消筛选[/yellow]")
            return
        
        findings = self.knowledge_base.get('key_findings', [])
        filtered = [f for f in findings if keyword.lower() in json.dumps(f, ensure_ascii=False).lower()]
        
        self.console.print(f"\n筛选结果: {len(filtered)}/{len(findings)} 条匹配 '{keyword}'")
        
        for i, f in enumerate(filtered[:5], 1):
            self.console.print(f"  {i}. {f.get('title', '')}")
    
    def _handle_knowledge_integration(self):
        """
        处理资料整合（需求#3 - 符合剧情合理性原则）
        """
        if not self.knowledge_base:
            self.console.print("[yellow]⚠️ 无资料可整合[/yellow]")
            return
        
        self.console.print("\n"+"─"*50)
        self.console.print("[bold]🔗 整合资料到创作[/bold]")
        self.console.print("─"*50)
        self.console.print("[dim]选择要重点融入创作的资料项[/dim]\n")
        
        findings = self.knowledge_base.get('key_findings', [])
        
        for i, finding in enumerate(findings[:10], 1):
            self.console.print(f"  {i}. {finding.get('title', '')}")
        
        selection = input("\n输入编号(多个用逗号分隔): ").strip()
        
        if not selection:
            self.console.print("[yellow]取消[/yellow]")
            return
        
        try:
            indices = [int(x.strip())-1 for x in selection.split(',') if x.strip().isdigit()]
            selected = [findings[i] for i in indices if 0 <= i < len(findings)]
            
            if selected:
                # 将选中的资料添加到创作指令中
                integration_note = f"\n【重点参考以下资料】:\n"
                for s in selected:
                    integration_note += f"- {s.get('title', '')}: {s.get('summary', '')[:80]}\n"
                
                self.console.print(f"\n[green]✅ 已选中 {len(selected)} 项资料，将在下次创作时优先参考[/green]")
                self.console.print(f"[dim]{integration_note[:200]}...[/dim]")
                
                # 记录审计
                self.constraint_mgr.audit_action(
                    action=AuditAction.MODIFY,
                    target_type="context",
                    target_id=self.story_id,
                    details=f"整合{len(selected)}项资料到创作上下文"
                )
            
        except ValueError:
            self.console.print("[red]❌ 格式错误[/red]")
    
    def show_constraints_panel(self):
        """显示约束条件面板（需求#4）"""
        if not self.constraint_mgr:
            self.console.print("[yellow]⚠️ 约束系统未初始化[/yellow]")
            return
        
        self.console.print("\n" + "="*60)
        self.console.print("[bold red]🔒 约束保障面板[/bold red]")
        self.console.print("="*60)
        
        # 导出完整报告
        report = self.constraint_mgr.export_audit_report()
        self.console.print(report)
    
    def show_audit_log(self):
        """显示审计日志（需求#4）"""
        if not self.constraint_mgr:
            self.console.print("[yellow]⚠️ 审计系统未初始化[/yellow]")
            return
        
        self.console.print("\n" + "="*60)
        self.console.print("[bold yellow]📋 审计日志[/bold yellow]")
        self.console.print("="*60)
        
        records = self.constraint_mgr.get_audit_history(limit=15)
        
        if not records:
            self.console.print("[dim]暂无审计记录[/dim]")
            return
        
        table = Table(show_header=True)
        table.add_column("时间", style="dim", width=20)
        table.add_column("动作", style="bold")
        table.add_column("对象", style="cyan")
        table.add_column("详情", max_width=40)
        
        for rec in records:
            time_str = rec.timestamp[:19].replace('T', ' ')
            action_icon = {
                'CREATE': '➕', 'MODIFY': '✏️', 'DELETE': '🗑',
                'CONFIRM': '✅', 'REJECT': '❌', 'ROLLBACK': '↩️'
            }.get(rec.action.value, '•')
            
            table.add_row(
                time_str,
                f"{action_icon} {rec.action.value}",
                rec.target_type,
                rec.details[:40] if rec.details else "-"
            )
        
        self.console.print(table)
        
        # 违规统计
        violation_report = self.constraint_mgr.get_violation_report()
        if violation_report['total_violations'] > 0:
            self.console.print(f"\n[yellow]⚠️ 违规统计: 总计{violation_report['total_violations']}次 | 未解决: {violation_report['unresolved']}次[/yellow]")
    
    async def run_packaging_phase(self):
        """打包阶段"""
        self.console.print("\n─"*60)
        self.console.print("[bold green]📦 打包存档[/bold green]")
        self.console.print("─"*60+"\n")
        
        self.display.update(SystemState.PACKAGING,"打包中...",90)
        
        # 最终保存完整小说
        full_novel = await self._save_full_novel()
        
        # ★★★ 最终审计报告 ★★★
        final_audit = self.constraint_mgr.export_audit_report()
        audit_path = self.output_dir / "_final_audit_report.txt"
        with open(audit_path, 'w', encoding='utf-8') as f:
            f.write(final_audit)
        self.console.print(f"[dim]   📋 审计报告已保存[/dim]")
        
        archiver = ZipArchiver()
        zip_path = archiver.create(self.story_id, self.output_dir)
        
        self.display.update(SystemState.PACKAGING,"完成!",100)
        self.is_finished = True
        
        total_words = sum(c['data']['word_count'] for c in self.chapters if c.get('data'))
        
        self.console.print(f"\n[bold green]🎉 小说创作完成！[/bold green]")
        self.console.print(f"📁 ZIP归档: {zip_path}")
        self.console.print(f"📂 故事ID: {self.story_id}")
        self.console.print(f"📊 统计: {len(self.chapters)}章, {total_words}字")
        self.console.print(f"📊 约束: {len(self.constraint_mgr.constraints)}项 | 审计: {len(self.constraint_mgr.audit_records)}条")
        self.console.print(f"📂 输出目录: {self.output_dir}\n")
    
    async def run_session(self):
        """
        运行持续性对话会话 - 完整闭环版本
        
        主循环（需求#2）：
        用户输入 → 导演验证 → 资料搜索 → 作家创作 → 用户确认 → 保存 → 下一章
        """
        self.show_banner()
        self.display.start()
        
        try:
            # 步骤1：获取初始创意
            user_input = input("💬 请输入您的故事创意: ").strip()
            if not user_input:
                self.console.print("[yellow]使用默认测试输入[/yellow]")
                user_input = "一个在2050年失去记忆的侦探，通过一本旧日记逐步找回自己身份的悬疑故事"
            
            # 步骤2：初始化（导演+研究员）+ 大纲确认 + 自动保存 + 约束注册
            await self.run_initialization_phase(user_input)
            
            # 步骤3：持续性写作循环（每章确认+自动保存+约束验证+审计记录）
            while not self.is_finished:
                self.console.print("\n" + "─"*60)
                self.console.print("[bold]准备进入下一轮创作[/bold]")
                self.console.print("─"*60)
                
                cmd_input = input("\n💭 命令 (回车继续/help查看更多): ").strip()
                command = self.parse_command(cmd_input)
                
                if command == UserCommand.QUIT:
                    self.console.print("\n👋 用户退出")
                    break
                
                elif command == UserCommand.HELP:
                    self.show_help()
                    continue
                
                elif command == UserCommand.STATUS:
                    self.show_status()
                    continue
                
                elif command == UserCommand.CONTEXT:
                    self.show_context_management()
                    continue
                
                elif command == UserCommand.CONSTRAINTS:
                    self.show_constraints_panel()
                    continue
                
                elif command == UserCommand.AUDIT:
                    self.show_audit_log()
                    continue
                
                elif command == UserCommand.FINISH:
                    await self.run_packaging_phase()
                    break
                
                elif command == UserCommand.MODIFY and self.chapters:
                    mod = input("✏️ 修改指令: ").strip()
                    if mod and self.chapters:
                        self.chapters[-1] = await self.writer.modify(
                            self.chapters[-1],mod,self.display
                        )
                        self.show_chapter(self.chapters[-1])
                        ch_num = len(self.chapters)
                        await self._save_novel_chapter(self.chapters[-1], ch_num)
                        await self._save_full_novel()
                    continue
                
                elif command == UserCommand.REGENERATE and self.chapters:
                    self.console.print("[dim]重新生成最后一章...[/dim]")
                    self.chapters.pop()
                    await self.run_writing_phase()
                    continue
                
                elif command == UserCommand.CONTINUE:
                    instructions = cmd_input if cmd_input else ""
                    await self.run_writing_phase(instructions=instructions)
                    continue
            
            # 最终状态
            self.display.update(SystemState.COMPLETED,"全部完成!",100)
            
        except KeyboardInterrupt:
            self.console.print("\n[yellow]⚠️ 用户中断[/yellow]")
            if self.chapters and not self.is_finished:
                if confirm("是否保存当前进度？"):
                    await self.run_packaging_phase()
        except Exception as e:
            self.console.print(f"\n[red]❌ 错误: {e}[/red]")
            import traceback
            traceback.print_exc()
        finally:
            self.display.stop()
            await self.cache.close()
            await self.logger.save_full()
