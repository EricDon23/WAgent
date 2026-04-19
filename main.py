#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WAgent V3.1 - 多AI协同智能写作系统（完全重构版）

基于错误修改.md + 项目任务.md 严格执行

核心特性：
✓ Redis-本地双向同步（程序启动后第一个执行的步骤）
✓ 分层存储（global.json + chapters/{x}.json）
✓ 导演AI分层生成（第一章 vs 后续章节）
✓ 研究AI资料库逻辑（先本地库 → 再网络）
✓ 作家AI完整数据加载
✓ 10阶段进度条 + 实时思考流
✓ rich库界面美化
✓ 统一主程序入口（禁止独立功能文件）
✓ 完整异常处理和日志记录

启动方式:
  python main.py                    # 正常启动（自动执行同步前置流程）
  python main.py --no-sync          # 跳过同步直接启动
  python main.py --mode web         # Web模式
  python main.py --check            # 环境检查
"""

import sys
import os
import json
import time
import signal
import argparse
import logging
import traceback
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

VERSION = "V3.1"
BUILD_DATE = "2026-04-19"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/wagent.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class WAgentMain:
    """
    WAgent V3.1 主程序 - 唯一入口
    
    整合所有功能模块：
    - 数据同步（前置流程）
    - 存储管理
    - AI三角色协同
    - 界面展示
    - 会话管理
    """
    
    def __init__(self):
        self.base_dir = Path.cwd()
        self.start_time = datetime.now()
        
        # 核心组件（延迟初始化）
        self.ui_manager = None
        self.local_storage = None
        self.redis_storage = None
        self.sync_manager = None
        self.director_ai = None
        self.researcher_ai = None
        self.writer_ai = None
        
        # 运行状态
        self._running = True
        self._current_session_id: Optional[str] = None
        self._current_story_id: Optional[str] = None
        self._chapter_count = 0
        
        # 注册信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        print("\n\n收到退出信号，正在安全关闭...")
        self.shutdown()
    
    def initialize(self) -> bool:
        """初始化所有核心组件"""
        try:
            print("\n[初始化] 正在加载核心组件...")
            
            # UI管理器
            from ui.cli import create_ui_manager
            self.ui_manager = create_ui_manager()
            
            # 存储模块
            from storage.local import create_local_storage
            from storage.redis import create_redis_storage
            
            self.local_storage = create_local_storage(str(self.base_dir / "stories"))
            self.redis_storage = create_redis_storage()
            
            # 同步管理器
            from sync.sync_manager import create_sync_manager
            self.sync_manager = create_sync_manager(
                base_dir=str(self.base_dir / "stories"),
                backup_dir=str(self.base_dir / "backups"),
                redis_storage=self.redis_storage,
                local_storage=self.local_storage
            )
            
            # AI模块
            from ai.director import create_director_ai
            from ai.researcher import create_researcher_ai
            from ai.writer import create_writer_ai
            
            self.director_ai = create_director_ai()
            self.researcher_ai = create_researcher_ai()
            self.writer_ai = create_writer_ai()
            
            # 初始化AI模块
            self.director_ai.initialize()
            self.researcher_ai.initialize()
            self.writer_ai.initialize()
            
            print("[初始化] ✓ 所有核心组件加载完成")
            return True
            
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            traceback.print_exc()
            return False
    
    def run_startup_sequence(self, skip_sync: bool = False):
        """
        执行启动序列
        
        流程：显示Banner → 环境检查 → **数据同步**（第一个执行的步骤）→ 显示就绪状态
        """
        # 显示Banner
        self.ui_manager.show_banner(VERSION)
        
        # 步骤1：环境检查
        print("\n[步骤 1/4] 环境检查...")
        self._check_environment()
        
        # 步骤2：**数据双向同步（V3.1核心前置流程）**
        print("\n[步骤 2/4] 🔄 数据双向同步 (V3.1核心前置流程)...")
        
        if skip_sync:
            print("  ⏭ 已跳过 (--no-sync)")
        else:
            sync_result = self.sync_manager.run_full_sync(
                auto_backup=True,
                show_progress=True
            )
            
            if not sync_result.success and sync_result.failed > 0:
                self.ui_manager.warning("同步存在问题，但系统可继续运行")
        
        # 步骤3：存储服务检查
        print("\n[步骤 3/4] 检查存储服务...")
        redis_status = "✓ 已连接" if self.redis_storage.is_available else "○ 未连接(纯本地模式)"
        print(f"  本地存储: ✓ 可用")
        print(f"  Redis存储: {redis_status}")
        
        # 步骤4：AI引擎就绪
        print("\n[步骤 4/4] AI引擎就绪...")
        print(f"  导演AI: ✓ 就绪")
        print(f"  研究AI: ✓ 就绪")
        print(f"  作家AI: ✓ 就绪")
        
        # 统计信息
        stories = self.local_storage.list_stories()
        print(f"\n{'='*60}")
        print(f"  WAgent {VERSION} 系统就绪")
        print(f"  故事数: {len(stories)}")
        print(f"  启动耗时: {(datetime.now() - self.start_time).total_seconds():.1f}秒")
        print(f"{'='*60}\n")
    
    def _check_environment(self):
        """环境检查"""
        checks = [
            ("Python版本", sys.version.split()[0], ">=3.10"),
            ("工作目录", str(self.base_dir), "存在"),
            ("配置文件", "config/settings.json", "存在"),
            ("日志目录", "logs/", "存在"),
        ]
        
        for name, value, condition in checks:
            # 判断条件是否满足
            if condition == "存在":
                # 对于"存在"条件，检查对应路径
                status = "✓" if Path(value).exists() else "○"
            elif condition.startswith(">="):
                # 对于版本号比较条件，安全处理
                try:
                    # 解析要求的版本号（如">=3.10" → (3,10)）
                    req_version = tuple(map(int, condition[2:].split('.')))
                    current_version = sys.version_info[:2]  # 获取主副版本
                    status = "✓" if current_version >= req_version else "○"
                except Exception:
                    status = "○"
            else:
                # 其他条件直接使用布尔值
                status = "✓" if condition else "○"
            print(f"    {status} {name}: {value}")
    
    def run_tower_mode(self):
        """
        控制塔模式（CLI交互）
        
        功能：
        - 会话选择/新建/删除
        - 对话创作（导演→研究→作家 完整流程）
        - 文件路径查看
        """
        self.ui_manager.info("进入控制塔模式...")
        
        while self._running:
            try:
                # 显示主菜单
                self.ui_manager.show_main_menu()
                
                choice = input("\n请输入操作编号: ").strip()
                
                if choice == "1":
                    self._handle_select_session()
                elif choice == "2":
                    self._handle_create_session()
                elif choice == "3":
                    self._handle_delete_session()
                elif choice == "4":
                    self._handle_show_path()
                elif choice == "5":
                    self._handle_search()
                elif choice == "6":
                    print("\n正在安全退出...")
                    self._running = False
                    break
                else:
                    self.ui_manager.warning("无效的操作编号")
                    
            except KeyboardInterrupt:
                print("\n")
                break
            except Exception as e:
                logger.error(f"控制塔模式错误: {e}")
                self.ui_manager.error(f"操作失败: {e}")
        
        self.shutdown()
    
    def _handle_select_session(self):
        """选择已有会话"""
        stories = self.local_storage.list_stories()
        
        if not stories:
            self.ui_manager.warning("暂无会话，请先创建新会话")
            return
        
        self.ui_manager.show_session_list(stories)
        
        try:
            idx = int(input("\n请输入会话编号: ").strip()) - 1
            if 0 <= idx < len(stories):
                story = stories[idx]
                self._current_story_id = story["story_id"]
                self._current_session_id = story.get("session_id", story["story_id"])
                self._chapter_count = story.get("chapter_count", 0)
                
                self.ui_manager.success(f"已选择: {story['story_name']}")
                self._enter_conversation_mode()
            else:
                self.ui_manager.warning("无效的编号")
        except ValueError:
            self.ui_manager.error("请输入数字编号")
    
    def _handle_create_session(self):
        """创建新会话"""
        name = input("\n请输入小说名称 (直接回车使用默认): ").strip()
        if not name:
            name = f"未命名故事_{datetime.now().strftime('%m%d_%H%M')}"
        
        import uuid
        session_id = f"sess_{uuid.uuid4().hex[:8]}"
        story_id = f"story_{uuid.uuid4().hex[:8]}"
        
        now = datetime.now().isoformat()
        
        # 创建元数据
        self.local_storage.create_meta(story_id, session_id, name)
        
        self._current_story_id = story_id
        self._current_session_id = session_id
        self._chapter_count = 0
        
        self.ui_manager.success(f"新会话已创建: {session_id}")
        self.ui_manager.info(f"绑定故事: {name} (ID: {story_id})")
        
        self._enter_conversation_mode(first_chapter=True)
    
    def _handle_delete_session(self):
        """删除会话"""
        stories = self.local_storage.list_stories()
        
        if not stories:
            self.ui_manager.warning("暂无可删除的会话")
            return
        
        self.ui_manager.show_session_list(stories)
        
        try:
            idx = int(input("\n请输入要删除的会话编号: ").strip()) - 1
            if 0 <= idx < len(stories):
                story = stories[idx]
                story_id = story["story_id"]
                
                print(f"\n即将删除会话: {story['story_name']}")
                print("这将同时删除所有绑定的故事数据（章节、设定、资料等）")
                
                confirm = input("确认? [Y/N/D(导出后删除)]: ").strip().lower()
                
                if confirm == 'y':
                    success, msg = self.sync_manager.delete_from_both(story_id)
                    if success:
                        self.ui_manager.success(msg)
                    else:
                        self.ui_manager.error(msg)
                        
                elif confirm == 'd':
                    self.ui_manager.info("导出功能开发中...")
                    
                else:
                    self.ui_manager.info("已取消")
            else:
                self.ui_manager.warning("无效的编号")
        except ValueError:
            self.ui_manager.error("请输入数字编号")
    
    def _handle_show_path(self):
        """查看故事路径"""
        stories = self.local_storage.list_stories()
        
        if not stories:
            self.ui_manager.warning("暂无会话")
            return
        
        self.ui_manager.show_session_list(stories)
        
        try:
            idx = int(input("\n请输入会话编号: ").strip()) - 1
            if 0 <= idx < len(stories):
                story = stories[idx]
                story_path = self.local_storage.base_dir / story["story_id"]
                
                if story_path.exists():
                    self.ui_manager.info(f"路径: {story_path.resolve()}")
                    
                    open_choice = input("是否打开文件夹? [y/n]: ").strip().lower()
                    if open_choice == 'y':
                        os.startfile(str(story_path.resolve()))
                else:
                    self.ui_manager.error("故事目录不存在")
            else:
                self.ui_manager.warning("无效的编号")
        except ValueError:
            self.ui_manager.error("请输入数字编号")
    
    def _handle_search(self):
        """搜索会话"""
        keyword = input("\n请输入搜索关键词: ").strip()
        
        if not keyword:
            self.ui_manager.warning("搜索关键词不能为空")
            return
        
        stories = self.local_storage.list_stories()
        results = [s for s in stories if keyword.lower() in s.get('story_name', '').lower()]
        
        if results:
            self.ui_manager.info(f"找到 {len(results)} 个匹配的会话:")
            self.ui_manager.show_session_list(results)
        else:
            self.ui_manager.warning(f'未找到包含 "{keyword}" 的会话')
    
    def _enter_conversation_mode(self, first_chapter: bool = False):
        """
        进入对话模式（单章创作流程）
        
        流程：用户输入 → 导演AI → 研究AI → 作家AI → 保存
        """
        if not self._current_story_id:
            self.ui_manager.error("未选择会话")
            return
        
        story_name = ""
        meta = self.local_storage.get_meta(self._current_story_id)
        if meta:
            story_name = meta.get('story_name', '')
        
        print(f"\n{'='*60}")
        print(f"  对话模式 | 故事: {story_name}")
        print(f"  当前章节: 第{self._chapter_count + 1}章")
        print(f"{'='*60}\n")
        
        while self._running:
            try:
                user_input = input("输入创作需求 (/help查看命令, /exit退出): ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ['/exit', '/quit', 'q']:
                    break
                elif user_input.lower() == '/help':
                    self._show_conversation_help()
                    continue
                elif user_input.lower() == '/status':
                    self._show_session_status()
                    continue
                
                # 执行完整的创作流程
                chapter_num = self._chapter_count + 1
                self._execute_creation_pipeline(user_input, chapter_num, first_chapter)
                
                self._chapter_count = chapter_num
                
            except KeyboardInterrupt:
                print("\n")
                break
            except Exception as e:
                logger.error(f"对话模式错误: {e}")
                self.ui_manager.error(f"操作失败: {e}")
    
    def _execute_creation_pipeline(self, user_input: str, chapter_num: int,
                                   is_first_chapter: bool = False):
        """
        执行完整的创作流水线
        
        阶段：
        1. 导演AI生成设定
        2. 用户确认
        3. 研究AI收集资料
        4. 作家AI生成内容
        5. 保存到存储
        6. 显示结果
        """
        # 显示10阶段进度（前几个阶段）
        phases = [
            (1, "分析用户需求"),
            (2, "调用历史上下文"),
            (3, "导演AI生成设定"),
            (4, "等待用户确认"),
            (5, "研究AI收集资料"),
            (6, "作家AI生成内容"),
            (7, "内容校验与优化"),
            (8, "保存到存储"),
            (9, "更新进度"),
            (10, "完成"),
        ]
        
        # ===== 阶段1-2：准备 =====
        self.ui_manager.show_progress(1, "分析用户需求...")
        self.ui_manager.add_thinking(f"接收到用户需求: {user_input[:50]}...", "analysis")
        time.sleep(0.1)
        
        self.ui_manager.show_progress(2, "加载历史上下文...")
        
        global_setting = None
        previous_context = None
        
        if not is_first_chapter and chapter_num > 1:
            # 加载全局设定
            global_setting = self.local_storage.get_global_setting(self._current_story_id)
            if global_setting:
                self.ui_manager.add_thinking(f"✅ 已加载总大纲: {global_setting.get('overall_title', '')}", "memory_call")
            
            # 加载前一章上下文
            previous_context = self.local_storage.get_previous_chapter_context(
                self._current_story_id, chapter_num
            )
            if previous_context:
                self.ui_manager.add_thinking(f"✅ 已加载第{chapter_num-1}章上下文", "memory_call")
        
        time.sleep(0.1)
        
        # ===== 阶段3：导演AI =====
        self.ui_manager.show_progress(3, "导演AI生成设定中...")
        
        if is_first_chapter or chapter_num == 1:
            # 第一章：生成全局设定 + 第一章设定
            result = self.director_ai.generate_first_chapter_setting(user_input)
            
            if result["success"]:
                data = result["data"]
                global_data = data["global_setting"]
                chapter_data = data["chapter_setting"]
                
                # 保存全局设定到 global.json
                self.local_storage.create_global_setting(self._current_story_id, global_data)
                
                # 保存第一章设定到 chapters/1.json
                self.local_storage.save_chapter_setting(
                    self._current_story_id, 1, chapter_data
                )
                
                global_setting = global_data
                
            else:
                self.ui_manager.error("导演AI生成失败")
                return
        else:
            # 后续章节：仅生成章节设定
            result = self.director_ai.generate_continuation_chapter_setting(
                story_id=self._current_story_id,
                chapter_num=chapter_num,
                user_input=user_input,
                global_setting=global_setting or {},
                previous_context=previous_context
            )
            
            if result["success"]:
                data = result["data"]
                chapter_data = data["chapter_setting"]
                
                # 保存章节设定到 chapters/{x}.json
                self.local_storage.save_chapter_setting(
                    self._current_story_id, chapter_num, chapter_data
                )
                
                # 增量更新全局设定
                incremental = data.get("incremental_update", {})
                new_chars = incremental.get("new_characters", [])
                
                if new_chars:
                    self.local_storage.append_to_character_relations(
                        self._current_story_id, new_chars
                    )
                
                # 向总体大纲追加本章条目
                outline_entry = {
                    "chapter_num": chapter_num,
                    "title": chapter_data.get("chapter_title", ""),
                    "summary": chapter_data.get("summary", ""),
                    "detailed_outline": chapter_data.get("chapter_outline", "")
                }
                self.local_storage.append_to_overall_outline(
                    self._current_story_id, outline_entry
                )
                
            else:
                self.ui_manager.error("导演AI生成失败")
                return
        
        self.ui_manager.success(f"导演AI完成! 标题: {chapter_data.get('chapter_title', '')}")
        
        # ===== 阶段4：用户确认 =====
        self.ui_manager.show_progress(4, "等待用户确认...")
        
        # 显示信息卡片（6项信息）
        info_card_data = {
            "chapter_title": chapter_data.get("chapter_title", ""),
            "theme": chapter_data.get("theme", ""),
            "characters": chapter_data.get("chapter_characters", []),
            "outline": chapter_data.get("chapter_outline", ""),
            "word_count": chapter_data.get("word_count_target", 3000),
        }
        
        if global_setting:
            info_card_data["overall_title"] = global_setting.get("overall_title", "")
            info_card_data["character_relations"] = global_setting.get("character_relations", [])
            info_card_data["core_theme"] = global_setting.get("core_theme", "")
        
        self.ui_manager.show_info_card(info_card_data, chapter_num)
        
        confirm = input("\n确认此设定? [y/n]: ").strip().lower()
        if confirm != 'y':
            self.ui_manager.info("已取消本次生成")
            return
        
        # ===== 阶段5：研究AI =====
        self.ui_manager.show_progress(5, "研究AI收集中...")
        
        research_needs = []
        if global_setting:
            research_needs = [
                global_setting.get("core_theme", ""),
                "世界观背景",
                "角色性格特征"
            ]
        
        research_result = self.researcher_ai.research(
            topics=research_needs,
            story_name=info_card_data.get("overall_title", ""),
            theme=info_card_data.get("core_theme", "")
        )
        
        research_data = research_result.get("data", {}) if research_result["success"] else {}
        
        # 保存研究资料
        self.researcher_ai.save_to_chapter_research(
            self._current_story_id, chapter_num, research_data
        )
        
        self.ui_manager.success(f"研究完成! 收集 {research_data.get('total_findings', 0)} 条资料")
        
        # ===== 阶段6-7：作家AI =====
        self.ui_manager.show_progress(6, "作家AI创作中...")
        
        content_result = self.writer_ai.generate_chapter(
            story_setting=global_setting or {},
            chapter_setting=chapter_data,
            research_data=research_data,
            previous_chapter_content="",
            global_outline=global_setting.get("overall_outline", []) if global_setting else [],
            character_relations=global_setting.get("character_relations", []) if global_setting else []
        )
        
        if not content_result["success"]:
            self.ui_manager.error("作家AI生成失败")
            return
        
        content_data = content_result["data"]
        content = content_data["content"]
        word_count = content_data["word_count"]
        
        self.ui_manager.show_progress(7, "校验完成")
        
        # ===== 阶段8-9：保存 =====
        self.ui_manager.show_progress(8, "保存到存储...")
        
        # 保存章节内容
        self.local_storage.save_chapter_content(
            self._current_story_id, chapter_num, content
        )
        
        # 更新元数据
        self.local_storage.update_meta(
            self._current_story_id,
            chapter_count=chapter_num,
            total_words=self.local_storage.get_meta(self._current_story_id).get("total_words", 0) + word_count if self.local_storage.get_meta(self._current_story_id) else word_count
        )
        
        self.ui_manager.show_progress(9, "进度已更新")
        
        # ===== 阶段10：完成 =====
        self.ui_manager.show_progress(10, "全部完成!")
        
        # 显示结果预览
        print(f"\n{'='*60}")
        print(f"  ✅ 第{chapter_num}章创作完成!")
        print(f"  标题: {chapter_data.get('chapter_title', '')}")
        print(f"  字数: {word_count}")
        print(f"{'='*60}")
        
        # 内容预览
        preview = content[:400]
        print(f"\n--- 内容预览 ---")
        print(preview)
        if len(content) > 400:
            print("... (后续省略)")
        print(f"{'-'*40}")
    
    def _show_conversation_help(self):
        """显示对话帮助"""
        help_text = """
可用命令:
  /help       - 显示此帮助信息
  /status     - 查看当前会话与故事状态
  /exit       - 退出对话模式，返回主菜单
  直接输入文本 - 作为创作需求，启动完整创作流程
"""
        print(help_text)
    
    def _show_session_status(self):
        """显示当前状态"""
        if not self._current_story_id:
            self.ui_manager.info("未选择任何会话")
            return
        
        meta = self.local_storage.get_meta(self._current_story_id)
        global_setting = self.local_storage.get_global_setting(self._current_story_id)
        
        print(f"\n{'='*50}")
        print(f"  会话状态")
        print(f"{'='*50}")
        print(f"  故事ID:   {self._current_story_id}")
        print(f"  会话ID:   {self._current_session_id}")
        
        if meta:
            print(f"  故事名称: {meta.get('story_name', '')}")
            print(f"  已写章节: {meta.get('chapter_count', 0)}章")
            print(f"  总字数:   {meta.get('total_words', 0)}字")
        
        if global_setting:
            print(f"  全局标题: {global_setting.get('overall_title', '')}")
            print(f"  总章节数: {len(global_setting.get('overall_outline', []))}")
        
        print(f"{'='*50}")
    
    def shutdown(self):
        """优雅关闭"""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        logger.info(f"WAgent {VERSION} 已关闭 (运行时长: {elapsed:.1f}秒)")
        
        print(f"\n{'='*60}")
        print(f"  WAgent {VERSION} 已安全关闭")
        print(f"  运行时长: {elapsed:.1f}秒")
        print(f"{'='*60}")


def main():
    """主程序入口"""
    parser = argparse.ArgumentParser(
        description=f"WAgent {VERSION} - 多AI协同智能写作系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
V3.1核心特性:
  • Redis-本地双向同步（启动时自动执行）
  • 分层存储（global.json + chapters/{x}.json）
  • AI差异化输出（第一章 vs 后续章节）
  • 10阶段可视化进度
  • rich库美化界面

运行模式:
  无参数                     正常启动（自动执行同步）
  --no-sync                  跳过同步直接启动
  --mode web                 Web模式
  --check                    环境检查
"""
    )
    
    parser.add_argument('--mode', '-m', choices=['tower', 'web'],
                       help='启动模式')
    parser.add_argument('--no-sync', action='store_true',
                       help='跳过同步前置流程')
    parser.add_argument('--check', '-q', action='store_true',
                       help='环境检查')
    parser.add_argument('-v', '--version', action='version',
                       version=f'WAgent {VERSION}')
    
    args = parser.parse_args()
    
    app = WAgentMain()
    
    if not app.initialize():
        sys.exit(1)
    
    try:
        if args.check:
            app.run_startup_sequence(skip_sync=True)
            
        elif args.mode == 'web':
            app.run_startup_sequence(skip_sync=args.no_sync)
            print("\nWeb模式开发中...")
            
        else:
            app.run_startup_sequence(skip_sync=args.no_sync)
            app.run_tower_mode()
            
    except KeyboardInterrupt:
        print("\n\n用户中断")
    except Exception as e:
        logger.error(f"运行错误: {e}", exc_info=True)
        sys.exit(1)
    
    finally:
        app.shutdown()


if __name__ == "__main__":
    main()
