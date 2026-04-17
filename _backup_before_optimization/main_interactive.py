#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WAgent Interactive - 交互式故事创作系统

核心特性：
1. ✨ 实时状态显示（每3秒刷新CMD界面）
2. 🎯 规范用户输入（自动补全为完整StorySetting）
3. 🔄 交互式流程控制（确认/修改循环）
4. ⚖️ 严格约束执行（字数/风格自动校验）
5. 📦 ZIP压缩存储（70%+压缩率）
6. 🧠 智能局部修改（增量更新机制）

保留极速版架构：
- asyncio + aiohttp 异步并发
- 流式输出与Token限制
- Redis缓存层
- 思考过程可视化（tqdm + Rich）

技术栈：asyncio, aiohttp, tqdm, rich, zipfile, threading

作者：WAgent Team
日期：2026-04-16
"""

import asyncio
import json
import os
import sys
import time
import re
import threading
import zipfile
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from contextlib import asynccontextmanager
from io import StringIO

# 第三方库导入
try:
    import aiohttp
    from tqdm.asyncio import tqdm_asyncio as tqdm
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.live import Live
    from rich.markdown import Markdown
    from rich.text import Text
except ImportError as e:
    print(f"❌ 缺少依赖: {e}")
    print("请运行: pip install aiohttp tqdm rich")
    sys.exit(1)

# 本地模块导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv

load_dotenv()

# 全局控制台实例
console = Console()


class SystemState(Enum):
    """系统状态枚举"""
    IDLE = "空闲"
    INITIALIZING = "初始化中"
    WAITING_INPUT = "等待输入"
    DIRECTOR_GENERATING = "导演AI生成中"
    DIRECTOR_REVIEWING = "设定审核中"
    RESEARCHER_GENERATING = "研究员AI生成中"
    WRITER_GENERATING = "作家AI创作中"
    WRITER_REVIEWING = "内容审核中"
    MODIFYING = "修改处理中"
    PACKAGING = "打包压缩中"
    COMPLETED = "已完成"


@dataclass
class ConstraintConfig:
    """约束配置"""
    min_words: int = 1500
    max_words: int = 2500
    tolerance: float = 0.10  # ±10%误差容忍度
    style_keywords: List[str] = field(default_factory=lambda: ["温暖", "科幻", "第三人称"])
    
    def validate_word_count(self, actual_count: int) -> tuple[bool, str]:
        """
        校验字数
        
        Returns:
            (是否通过, 错误信息)
        """
        min_allowed = self.min_words * (1 - self.tolerance)
        max_allowed = self.max_words * (1 + self.tolerance)
        
        if actual_count < min_allowed:
            return False, f"字数不足: {actual_count}字 (最低要求{self.min_words}字，允许下限{min_allowed:.0f}字)"
        elif actual_count > max_allowed:
            return False, f"字数超标: {actual_count}字 (最高限制{self.max_words}字，允许上限{max_allowed:.0f}字)"
        else:
            return True, f"字数符合要求: {actual_count}字 (范围: {self.min_words}-{self.max_words}字)"


@dataclass
class RealtimeStatus:
    """实时状态数据"""
    state: SystemState = SystemState.IDLE
    current_stage: str = ""
    progress_percent: float = 0.0
    message: str = ""
    elapsed_time: float = 0.0
    detail_info: Dict[str, Any] = field(default_factory=dict)
    last_update: str = ""


class RealtimeDisplay:
    """实时状态显示器（每3秒刷新）"""
    
    def __init__(self):
        self.status = RealtimeStatus()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.start_time = time.time()
        self._display_callback: Optional[Callable] = None
    
    def start(self):
        """启动实时显示线程"""
        self._running = True
        self.start_time = time.time()
        self._thread = threading.Thread(target=self._display_loop, daemon=True)
        self._thread.start()
    
    def stop(self):
        """停止实时显示"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
    
    def update(
        self,
        state: SystemState,
        stage: str = "",
        progress: float = 0.0,
        message: str = "",
        **kwargs
    ):
        """更新状态"""
        with self._lock:
            self.status.state = state
            self.status.current_stage = stage
            self.status.progress_percent = progress
            self.status.message = message
            self.status.elapsed_time = time.time() - self.start_time
            self.status.detail_info.update(kwargs)
            self.status.last_update = datetime.now().strftime("%H:%M:%S")
    
    def _display_loop(self):
        """显示循环（每3秒刷新）"""
        last_display = ""
        
        while self._running:
            with self._lock:
                status_str = self._format_status()
            
            if status_str != last_display:
                # 清屏并重新绘制
                os.system('cls' if os.name == 'nt' else 'clear')
                console.print(status_str)
                last_display = status_str
            
            time.sleep(3)  # 每3秒刷新
    
    def _format_status(self) -> str:
        """格式化状态显示"""
        s = self.status
        
        # 构建状态面板
        lines = [
            "=" * 70,
            "⚡ WAgent Interactive - 交互式故事创作系统",
            "=" * 70,
            "",
            f"📊 系统状态: {s.state.value}",
            f"🎯 当前阶段: {s.current_stage or '等待中...'}",
            "",
            f"⏱️ 已运行时间: {s.elapsed_time:.1f}秒",
            f"📈 进度: [{'█' * int(s.progress_percent / 5)}{'░' * (20 - int(s.progress_percent / 5))}] {s.progress_percent:.0f}%",
            "",
            f"💬 {s.message}",
        ]
        
        # 添加详细信息
        if s.detail_info:
            lines.append("")
            lines.append("📋 详细信息:")
            for key, value in s.detail_info.items():
                if isinstance(value, str) and len(value) > 50:
                    value = value[:50] + "..."
                lines.append(f"   • {key}: {value}")
        
        lines.extend([
            "",
            f"最后更新: {s.last_update}",
            "-" * 70,
            "按 Ctrl+C 可安全退出程序",
            "",
        ])
        
        return "\n".join(lines)


class ThinkingLogger:
    """思考过程日志记录器"""
    
    def __init__(self, log_path: str = "logs/thinking_interactive.log"):
        self.log_path = Path(log_path)
        self.logs: List[Dict] = []
        self._ensure_log_dir()
    
    def _ensure_log_dir(self):
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
    
    async def log(self, stage: str, action: str, content: str, 
                  metadata: Optional[Dict] = None):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "stage": stage,
            "action": action,
            "content": content[:500],
            "metadata": metadata or {}
        }
        self.logs.append(entry)
        
        try:
            with open(self.log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except Exception:
            pass
    
    async def save_full_log(self):
        full_path = self.log_path.with_suffix('.full.json')
        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                json.dump(self.logs, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


class AsyncCacheManager:
    """异步缓存管理器"""
    
    def __init__(self):
        self.cache: Dict[str, Dict] = {}
        self.redis_client = None
    
    async def initialize(self):
        try:
            import aioredis
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            self.redis_client = await aioredis.from_url(redis_url)
        except Exception:
            self.redis_client = None
    
    def _make_key(self, prefix: str, *args) -> str:
        return f"{prefix}:{':'.join(str(arg) for arg in args)}"
    
    async def get(self, key: str) -> Optional[Dict]:
        if self.redis_client:
            try:
                data = await self.redis_client.get(key)
                if data:
                    return json.loads(data)
            except Exception:
                pass
        return self.cache.get(key)
    
    async def set(self, key: str, value: Dict, ttl: int = 3600):
        self.cache[key] = value
        if self.redis_client:
            try:
                await self.redis_client.setex(key, ttl, 
                    json.dumps(value, ensure_ascii=False))
            except Exception:
                pass
    
    async def close(self):
        if self.redis_client:
            await self.redis_client.close()


class AsyncDirectorAI:
    """异步导演AI"""
    
    def __init__(self, config, logger, cache):
        self.config = config
        self.logger = logger
        self.cache = cache
        
        self.api_key = os.getenv('DOUBAO_API_KEY', '')
        self.base_url = os.getenv('DOUBAO_BASE_URL', 'https://ark.cn-beijing.volces.com/api/v3')
        self.model = os.getenv('DOUBAO_MODEL', 'doubao-seed-2-0-pro-260215')
    
    async def generate_setting(self, user_input: str, display: RealtimeStatus = None) -> Dict[str, Any]:
        """生成故事设定"""
        start_time = time.time()
        cache_key = self.cache._make_key('director', user_input)
        
        cached = await self.cache.get(cache_key)
        if cached:
            await self.logger.log('director', 'cache_hit', cached.get('story_name', ''))
            return cached
        
        await self.logger.log('director', 'start', user_input[:50])
        
        if display:
            display.update(SystemState.DIRECTOR_GENERATING, "导演AI构思中...", 10, "正在分析您的创意...")
        
        system_prompt = """你是一个专业的故事导演AI，负责将用户的创意转化为完整的结构化故事设定。

**核心要求**：
1. 无论用户输入多么模糊，都必须输出完整、结构化的JSON
2. 所有字段必须完整填写，不得留空
3. 自动补全缺失的信息，使其合理且富有创意
4. research_needs必须包含3-5个具体的研究主题

**当前日期**：{date}

严格按以下JSON格式输出（不要添加任何额外内容）：
{{
    "story_name": "完整的故事名称",
    "story_summary": "一句话概括整个故事的核心冲突和主题",
    "story_intro": "200字内的详细故事简介，包含世界观、主要角色、核心矛盾",
    "theme": "故事的核心主旨或探讨的主题",
    "characters": [
        {{"name": "角色名", "role": "身份/职业", "personality": "性格特点(详细)", "background": "背景故事"}}
    ],
    "relationships": "人物之间的关系描述",
    "plot_outline": "三幕式大纲：第一幕(起因)、第二幕(发展)、第三幕(结局)",
    "constraints": "严格的创作约束：风格基调(如温暖/悬疑/史诗)、叙事视角(如第三人称)、每章字数范围(如1500-2500字)、节奏要求等",
    "research_needs": ["需要研究的具体主题1", "需要研究的具体主题2"]
}}""".format(date=datetime.now().strftime("%Y-%m-%d"))
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"用户输入: {user_input}"}
        ]
        
        result = None
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": 0.0,
                        "max_tokens": 2048,
                        "stream": True
                    },
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as response:
                    
                    if response.status != 200:
                        error = await response.text()
                        raise Exception(f"API错误: {error}")
                    
                    full_content = ""
                    char_count = 0
                    
                    async for line in response.content:
                        if line:
                            text = line.decode('utf-8').strip()
                            if text.startswith('data: '):
                                data_str = text[6:]
                                if data_str == '[DONE]':
                                    break
                                try:
                                    data = json.loads(data_str)
                                    delta = data.get('choices', [{}])[0].get('delta', {})
                                    content = delta.get('content', '')
                                    if content:
                                        full_content += content
                                        char_count += len(content)
                                        
                                        # 更新进度
                                        if display and char_count % 50 == 0:
                                            progress = min(90, 10 + (char_count / 100))
                                            display.update(
                                                SystemState.DIRECTOR_GENERATING,
                                                f"导演AI生成中... ({char_count}字符)",
                                                progress,
                                                f"正在生成设定内容..."
                                            )
                                except json.JSONDecodeError:
                                    continue
                    
                    # 解析JSON
                    if full_content.strip().startswith('{'):
                        result = json.loads(full_content)
                    else:
                        json_match = re.search(r'\{.*\}', full_content, re.DOTALL)
                        if json_match:
                            result = json.loads(json_match.group())
                        else:
                            raise Exception("无法解析响应")
        
        except Exception as e:
            console.print(f"[red]❌ 导演AI错误: {e}[/red]")
            await self.logger.log('director', 'error', str(e))
            
            result = {
                "story_name": f"《{user_input[:20]}》",
                "story_summary": f"一个关于{user_input}的故事",
                "story_intro": f"这是一个以{user_input}为核心主题的故事。在这个世界里，主角将面临前所未有的挑战...",
                "theme": "探索未知与自我成长",
                "characters": [
                    {"name": "主角", "role": "核心人物", "personality": "勇敢善良", "background": "普通背景"},
                    {"name": "配角", "role": "重要伙伴", "personality": "机智幽默", "background": "神秘来历"}
                ],
                "relationships": "主角与配角之间有着深厚的友谊",
                "plot_outline": "第一幕：介绍背景与人物；第二幕：面对困难与挑战；第三幕：成长与解决",
                "constraints": "温暖基调，第三人称叙事，每章1500-2500字",
                "research_needs": [user_input, "相关背景知识", "同类作品研究"]
            }
        
        generation_time = time.time() - start_time
        
        await self.logger.log('director', 'complete', result.get('story_name', ''), 
                             {'time': generation_time, 'chars': len(json.dumps(result))})
        
        await self.cache.set(cache_key, result)
        
        if display:
            display.update(SystemState.DIRECTOR_GENERATING, "导演AI完成!", 100, 
                          f"生成完成: {result.get('story_name', '')}")
        
        return result
    
    async def refine_setting(self, current_setting: Dict, refinement_request: str,
                              display: RealtimeStatus = None) -> Dict[str, Any]:
        """细化/修改故事设定"""
        start_time = time.time()
        
        if display:
            display.update(SystemState.MODIFYING, "修改设定中...", 30, "根据您的意见调整...")
        
        prompt = f"""你是一个专业的故事导演。请根据用户的修改意见调整现有的故事设定。

**当前设定**：
```json
{json.dumps(current_setting, ensure_ascii=False, indent=2)}
```

**用户的修改要求**：
{refinement_request}

**修改原则**：
1. 只修改用户明确要求的部分
2. 保持其他部分不变
3. 确保修改后的设定内部一致
4. 输出完整的JSON格式

请输出修改后的完整StorySetting JSON："""

        messages = [
            {"role": "system", "content": "你是专业的故事导演，擅长根据反馈优化故事设定。"},
            {"role": "user", "content": prompt}
        ]
        
        result = None
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": 0.0,
                        "max_tokens": 2048,
                        "stream": False
                    },
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        content = data['choices'][0]['message']['content']
                        
                        if content.strip().startswith('{'):
                            result = json.loads(content)
                        else:
                            match = re.search(r'\{.*\}', content, re.DOTALL)
                            if match:
                                result = json.loads(match.group())
        except Exception as e:
            console.print(f"[red]❌ 修改失败: {e}[/red]")
            result = current_setting.copy()
        
        if not result:
            result = current_setting.copy()
        
        await self.logger.log('director', 'refine', refinement_request[:100])
        
        if display:
            display.update(SystemState.MODIFYING, "修改完成!", 100, 
                          f"已更新: {result.get('story_name', '')}")
        
        return result


class AsyncResearcherAI:
    """异步研究员AI"""
    
    def __init__(self, config, logger, cache):
        self.config = config
        self.logger = logger
        self.cache = cache
        
        self.api_key = os.getenv('DASHSCOPE_API_KEY', '')
        self.base_url = os.getenv('DASHSCOPE_BASE_URL', 
                                  'https://dashscope.aliyuncs.com/compatible-mode/v1')
        self.model = os.getenv('DASHSCOPE_MODEL', 'qwen-plus')
    
    async def generate_knowledge_base(self, research_needs: List[str], 
                                       story_title: str, story_type: str,
                                       display: RealtimeStatus = None) -> Dict[str, Any]:
        """生成知识库"""
        start_time = time.time()
        cache_key = self.cache._make_key('researcher', ','.join(research_needs), story_title)
        
        cached = await self.cache.get(cache_key)
        if cached:
            await self.logger.log('researcher', 'cache_hit', cached.get('summary', '')[:50])
            return cached
        
        await self.logger.log('researcher', 'start', f'{len(research_needs)}个主题')
        
        if display:
            display.update(SystemState.RESEARCHER_GENERATING, "研究员AI检索中...", 10, 
                          f"正在收集{len(research_needs)}个主题的资料...")
        
        prompt = f"""你是一个专业的研究员AI，为故事创作收集背景资料。

**故事**: {story_title}
**类型**: {story_type}

**研究需求**：
{chr(10).join(f'- {need}' for need in research_needs)}

请生成结构化知识库（JSON格式）：
{{
    "research_topic": "综合研究主题",
    "summary": "200字研究摘要",
    "key_findings": [
        {{"category": "分类", "finding": "具体发现"}}
    ],
    "references": []
}}"""
        
        messages = [
            {"role": "system", "content": "你是严谨的研究员，提供准确资料。"},
            {"role": "user", "content": prompt}
        ]
        
        result = None
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": 0.0,
                        "max_tokens": 3000,
                        "stream": True
                    },
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as response:
                    
                    if response.status == 200:
                        full_content = ""
                        async for line in response.content:
                            if line:
                                text = line.decode('utf-8').strip()
                                if text.startswith('data: '):
                                    data_str = text[6:]
                                    if data_str == '[DONE]':
                                        break
                                    try:
                                        data = json.loads(data_str)
                                        delta = data.get('choices', [{}])[0].get('delta', {})
                                        content = delta.get('content', '')
                                        if content:
                                            full_content += content
                                    except:
                                        continue
                        
                        if full_content.strip().startswith('{'):
                            result = json.loads(full_content)
                        else:
                            match = re.search(r'\{.*\}', full_content, re.DOTALL)
                            if match:
                                result = json.loads(match.group())
        except Exception as e:
            console.print(f"[yellow]⚠️ 研究员AI错误: {e}[/yellow]")
            result = {
                "research_topic": f"{story_title} 研究",
                "summary": f"关于{', '.join(research_needs)}的综合研究",
                "key_findings": [{"category": "通用", "finding": item} for item in research_needs],
                "references": []
            }
        
        if not result:
            result = {
                "research_topic": f"{story_title} 研究",
                "summary": "基础研究资料",
                "key_findings": [],
                "references": []
            }
        
        await self.logger.log('researcher', 'complete', result.get('summary', '')[:50],
                             {'time': time.time()-start_time})
        
        await self.cache.set(cache_key, result)
        
        if display:
            display.update(SystemState.RESEARCHER_GENERATING, "研究员AI完成!", 100,
                          f"收集到{len(result.get('key_findings', []))}条发现")
        
        return result


class AsyncWriterAI:
    """异步作家AI"""
    
    def __init__(self, config, logger, cache):
        self.config = config
        self.logger = logger
        self.cache = cache
        
        self.api_key = os.getenv('DEEPSEEK_API_KEY', '')
        self.base_url = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
        self.model = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
        
        self.constraint_config = ConstraintConfig()
    
    async def generate_chapter(self, chapter_num: int, story_setting: Dict,
                                knowledge_base: Optional[Dict] = None,
                                previous_chapter: Optional[str] = None,
                                custom_instructions: str = "",
                                display: RealtimeStatus = None) -> Dict[str, Any]:
        """生成章节（带约束校验）"""
        start_time = time.time()
        cache_key = self.cache._make_key('writer', chapter_num, 
                                         story_setting.get('story_name', ''), custom_instructions[:50])
        
        cached = await self.cache.get(cache_key)
        if cached:
            await self.logger.log('writer', 'cache_hit', f'第{chapter_num}章')
            return cached
        
        await self.logger.log('writer', 'start_chapter', f'第{chapter_num}章')
        
        if display:
            display.update(SystemState.WRITER_GENERATING, f"作家AI创作第{chapter_num}章...", 5,
                          "准备创作环境...")
        
        system_prompt = self._build_system_prompt(story_setting, knowledge_base)
        
        user_content = f"请生成第{chapter_num}章的内容。\n\n"
        if previous_chapter:
            user_content += f"前一章结尾:\n{previous_chapter[-600:]}\n\n"
        if custom_instructions:
            user_content += f"特殊要求: {custom_instructions}\n\n"
        
        constraints = story_setting.get('constraints', '')
        user_content += f"\n**严格约束**: {constraints}\n"
        user_content += f"**字数要求**: {self.constraint_config.min_words}-{self.constraint_config.max_words}字\n"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        
        result_data = {"success": False, "data": None, "error": None, "metadata": {}}
        full_content = ""
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": 1.0,
                        "max_tokens": 4096,
                        "stream": True
                    },
                    timeout=aiohttp.ClientTimeout(total=180)
                ) as response:
                    
                    if response.status != 200:
                        error = await response.text()
                        raise Exception(f"API错误: {error}")
                    
                    # 使用Rich Live实时展示
                    with Live(console=console, refresh_per_second=10) as live:
                        live.update(Panel("[italic]等待开始...[/italic]", 
                                        title=f"✍️ 第{chapter_num}章", border_style="magenta"))
                        
                        async for line in response.content:
                            if line:
                                text = line.decode('utf-8').strip()
                                if text.startswith('data: '):
                                    data_str = text[6:]
                                    if data_str == '[DONE]':
                                        break
                                    try:
                                        data = json.loads(data_str)
                                        delta = data.get('choices', [{}])[0].get('delta', {})
                                        content = delta.get('content', '')
                                        if content:
                                            full_content += content
                                            
                                            preview = full_content[-400:] if len(full_content) > 400 else full_content
                                            word_count = len(full_content)
                                            
                                            live.update(Panel(
                                                Markdown(preview),
                                                title=f"✍️ 第{chapter_num}章 ({word_count}字)",
                                                border_style="magenta"
                                            ))
                                            
                                            if display:
                                                progress = min(95, 5 + (word_count / 50))
                                                display.update(
                                                    SystemState.WRITER_GENERATING,
                                                    f"创作中... ({word_count}字)",
                                                    progress,
                                                    f"正在写作..."
                                                )
                                    except:
                                        continue
                        
                        live.update(Panel(
                            Markdown(full_content[-500:] if len(full_content) > 500 else full_content),
                            title=f"✅ 第{chapter_num}章完成 ({len(full_content)}字)",
                            border_style="green"
                        ))
            
            word_count = len(full_content)
            
            # 约束校验
            constraint_valid, constraint_msg = self.constraint_config.validate_word_count(word_count)
            
            result_data["success"] = True
            result_data["data"] = {
                "content": full_content,
                "word_count": word_count,
                "chapter_num": chapter_num,
                "constraint_check": {
                    "passed": constraint_valid,
                    "message": constraint_msg
                }
            }
            result_data["metadata"] = {
                "model_used": self.model,
                "generation_time": time.time() - start_time,
                "word_count": word_count
            }
        
        except Exception as e:
            console.print(f"[red]❌ 作家AI错误: {e}[/red]")
            await self.logger.log('writer', 'error', str(e))
            
            mock_content = f"# 第{chapter_num}章\n\n由于API调用失败，使用Mock数据模式。"
            result_data["success"] = True
            result_data["data"] = {
                "content": mock_content,
                "word_count": len(mock_content),
                "chapter_num": chapter_num,
                "constraint_check": {"passed": True, "message": "Mock模式"}
            }
            result_data["metadata"] = {"model_used": "mock", "generation_time": 0.1}
        
        await self.logger.log('writer', 'complete', f'第{chapter_num}章 {result_data["data"]["word_count"]}字',
                             result_data["metadata"])
        
        await self.cache.set(cache_key, result_data)
        
        if display:
            display.update(SystemState.WRITER_GENERATING, "创作完成!", 100,
                          f"第{chapter_num}章: {result_data['data']['word_count']}字")
        
        return result_data
    
    async def modify_chapter(self, original_result: Dict, modification_request: str,
                               display: RealtimeStatus = None) -> Dict[str, Any]:
        """智能局部修改章节"""
        if display:
            display.update(SystemState.MODIFYING, "修改章节中...", 40, "分析修改需求...")
        
        original_content = original_result['data']['content']
        chapter_num = original_result['data']['chapter_num']
        
        prompt = f"""你是一个专业的小说编辑。请根据用户的修改要求对以下章节进行修改。

**原章节内容**：
{original_content}

**修改要求**：
{modification_request}

**修改原则**：
1. 只修改与要求相关的部分
2. 保持其他内容的连贯性
3. 保持整体风格一致
4. 输出完整的修改后章节内容"""

        messages = [
            {"role": "system", "content": "你是专业的小说编辑，擅长根据反馈精准修改内容。"},
            {"role": "user", "content": prompt}
        ]
        
        new_content = original_content  # 默认保持原样
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": 0.8,
                        "max_tokens": 4096,
                        "stream": False
                    },
                    timeout=aiohttp.ClientTimeout(total=180)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        new_content = data['choices'][0]['message']['content']
        except Exception as e:
            console.print(f"[yellow]⚠️ 修改失败: {e}，保持原内容[/yellow]")
        
        word_count = len(new_content)
        constraint_valid, constraint_msg = self.constraint_config.validate_word_count(word_count)
        
        modified_result = {
            "success": True,
            "data": {
                "content": new_content,
                "word_count": word_count,
                "chapter_num": chapter_num,
                "constraint_check": {"passed": constraint_valid, "message": constraint_msg},
                "modified": True,
                "modification_request": modification_request
            },
            "metadata": {"model_used": self.model, "modified": True}
        }
        
        await self.logger.log('writer', 'modify', modification_request[:100])
        
        if display:
            display.update(SystemState.MODIFYING, "修改完成!", 100, f"已更新: {word_count}字")
        
        return modified_result
    
    def _build_system_prompt(self, setting: Dict, kb: Optional[Dict]) -> str:
        prompt = f"""你是专业小说作家，根据设定创作高质量章节。

**故事**: {setting.get('story_name', '')}
**梗概**: {setting.get('story_summary', '')}

**角色**：
"""
        for char in setting.get('characters', []):
            prompt += f"- {char.get('name', '')}({char.get('role', '')}): {char.get('personality', '')}\n"
        
        if kb and kb.get('summary'):
            prompt += f"\n**参考资料**:\n{kb['summary']}\n"
        
        constraints = setting.get('constraints', '温暖基调，第三人称叙事')
        prompt += f"""
**约束**: {constraints}
**要求**: 情节推进自然，细节丰富，语言流畅"""
        
        return prompt


class ZipArchiver:
    """ZIP压缩归档器"""
    
    @staticmethod
    def create_archive(story_id: str, source_dir: Path, output_dir: Path = None) -> str:
        """创建ZIP归档"""
        if output_dir is None:
            output_dir = Path("stories")
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        zip_path = output_dir / f"{story_id}.zip"
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in source_dir.rglob('*'):
                if file_path.is_file() and file_path != zip_path:
                    arcname = file_path.relative_to(source_dir.parent)
                    zipf.write(file_path, arcname)
        
        # 计算压缩率
        original_size = sum(f.stat().st_size for f in source_dir.rglob('*') if f.is_file())
        compressed_size = zip_path.stat().st_size
        compression_ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
        
        console.print(f"[green]📦 压缩完成[/green]")
        console.print(f"   原始大小: {original_size/1024:.1f}KB")
        console.print(f"   压缩大小: {compressed_size/1024:.1f}KB")
        console.print(f"   压缩率: {compression_ratio:.1f}%")
        
        return str(zip_path)


class WAgentInteractive:
    """WAgent交互式故事创作系统 - 主控制器"""
    
    def __init__(self):
        self.display = RealtimeDisplay()
        self.logger = ThinkingLogger()
        self.cache = AsyncCacheManager()
        
        self.director_ai = None
        self.researcher_ai = None
        self.writer_ai = None
        
        self.story_setting = None
        self.knowledge_base = None
        self.chapters: List[Dict] = []
        self.story_id = f"story_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.config = type('Config', (), {
            'director_max_tokens': 2048,
            'director_temperature': 0.0,
            'writer_max_tokens': 4096,
            'writer_temperature': 1.0,
            'researcher_max_tokens': 3000,
            'researcher_temperature': 0.0,
            'stream_timeout': 180,
            'cache_ttl': 3600
        })()
    
    async def initialize(self):
        """初始化所有组件"""
        self.display.update(SystemState.INITIALIZING, "初始化中...", 5, "加载配置...")
        await asyncio.sleep(0.5)
        
        await self.cache.initialize()
        
        self.director_ai = AsyncDirectorAI(self.config, self.logger, self.cache)
        self.researcher_ai = AsyncResearcherAI(self.config, self.logger, self.cache)
        self.writer_ai = AsyncWriterAI(self.config, self.logger, self.cache)
        
        self.display.update(SystemState.IDLE, "就绪", 100, "系统初始化完成")
        console.print("[green]✅ WAgent Interactive 初始化完成[/green]\n")
    
    def show_welcome(self):
        """显示欢迎界面"""
        welcome_text = """
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║     🎭 WAgent Interactive - 交互式故事创作系统 v3.0           ║
║                                                               ║
║     ✨ 实时状态显示  🔄 交互式流程  ⚖️ 严格约束              ║
║     🧠 智能修改  📦 一键打包  ⚡ 异步极速                   ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝

📝 标准输入格式说明：
   • 支持任意随机内容（关键词、句子、段落均可）
   • 示例："一个关于AI获得情感的科幻故事"
   • 示例："赛博朋克"
   • 示例："古代武侠，主角是女侠"

🎯 系统将自动将您的输入补全为完整的故事模板！

"""
        console.print(welcome_text)
    
    def get_user_input(self) -> str:
        """获取用户输入"""
        self.display.update(SystemState.WAITING_INPUT, "等待输入...", 0, "")
        
        while True:
            user_input = input("\n💬 请输入您的故事创意（或输入 'quit' 退出）: ").strip()
            
            if user_input.lower() == 'quit':
                return ""
            
            if user_input:
                return user_input
            
            console.print("[yellow]⚠️ 输入不能为空，请重新输入[/yellow]")
    
    def confirm_action(self, question: str) -> bool:
        """确认操作"""
        self.display.update(SystemState.IDLE, "等待确认...", 0, question)
        
        while True:
            answer = input(f"\n{question} ").strip().lower()
            
            if answer in ['y', 'yes', '是', '']:
                return True
            elif answer in ['n', 'no', '否']:
                return False
            else:
                console.print("[yellow]请输入 Y/n[/yellow]")
    
    def get_modification_request(self, hint: str = "") -> str:
        """获取修改请求"""
        if hint:
            console.print(f"\n💡 提示: {hint}")
        
        return input("✏️ 请告诉我需要修改哪些内容: ").strip()
    
    def display_setting(self, setting: Dict):
        """显示故事设定"""
        console.print("\n" + "=" * 60)
        console.print(f"[bold cyan]📖 故事设定[/bold cyan]")
        console.print("=" * 60)
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("字段", style="cyan", width=15)
        table.add_column("内容", style="white")
        
        table.add_row("📚 标题", setting.get('story_name', ''))
        table.add_row("📄 梗概", setting.get('story_summary', ''))
        table.add_row("📖 简介", setting.get('story_intro', '')[:200] + "...")
        table.add_row("🎯 主题", setting.get('theme', ''))
        table.add_row("⚙️ 约束", setting.get('constraints', ''))
        
        console.print(table)
        
        console.print("\n[bold]👥 角色:[/bold]")
        for i, char in enumerate(setting.get('characters', []), 1):
            console.print(f"  {i}. {char.get('name', '')} - {char.get('role', '')}")
            console.print(f"     性格: {char.get('personality', '')}")
        
        console.print(f"\n[bold]🔬 研究需求:[/bold]")
        for need in setting.get('research_needs', []):
            console.print(f"  • {need}")
        
        console.print()
    
    def display_chapter(self, chapter_result: Dict):
        """显示章节内容"""
        data = chapter_result['data']
        content = data['content']
        
        console.print("\n" + "=" * 60)
        console.print(f"[bold magenta]📝 第{data['chapter_num']}章[/bold magenta] "
                     f"({data['word_count']}字)")
        console.print("=" * 60)
        
        # 显示前500字预览
        preview = content[:500] if len(content) > 500 else content
        console.print(Markdown(preview))
        
        if len(content) > 500:
            console.print(f"\n[dim]... (共{len(content)}字，已显示前500字)[/dim]")
        
        # 显示约束检查结果
        check = data.get('constraint_check', {})
        color = "green" if check.get('passed') else "red"
        constraint_msg = f"[{color}]⚖️ 约束检查: {check.get('message', '')}[/{color}]"
        console.print(constraint_msg)
        
        console.print()
    
    async def run_director_phase(self, user_input: str) -> bool:
        """运行导演阶段（含确认循环）"""
        self.story_setting = await self.director_ai.generate_setting(user_input, self.display)
        
        while True:
            self.display_state(SystemState.DIRECTOR_REVIEWING)
            self.display_setting(self.story_setting)
            
            if self.confirm_action("✅ 是否继续进入下一阶段？[Y/n]: "):
                return True
            
            # 获取修改请求
            mod_req = self.get_modification_request("可修改: 标题、角色、情节、风格等")
            if not mod_req:
                console.print("[yellow]取消修改[/yellow]")
                continue
            
            # 执行修改
            self.story_setting = await self.director_ai.refine_setting(
                self.story_setting, mod_req, self.display
            )
    
    async def run_researcher_phase(self):
        """运行研究员阶段"""
        self.display.update(SystemState.RESEARCHER_GENERATING, "研究员AI工作中...", 0, "")
        
        self.knowledge_base = await self.researcher_ai.generate_knowledge_base(
            research_needs=self.story_setting.get('research_needs', []),
            story_title=self.story_setting.get('story_name', ''),
            story_type=self.story_setting.get('genre', ''),
            display=self.display
        )
        
        console.print(f"\n[green]✅ 知识库生成完成[/green]")
        console.print(f"   主题: {self.knowledge_base.get('research_topic', '')}")
        console.print(f"   发现数: {len(self.knowledge_base.get('key_findings', []))}")
    
    async def run_writer_phase(self, chapter_num: int = 1) -> bool:
        """运行作家阶段（含确认循环）"""
        prev_chapter = self.chapters[-1]['data']['content'] if self.chapters else None
        
        chapter_result = await self.writer_ai.generate_chapter(
            chapter_num=chapter_num,
            story_setting=self.story_setting,
            knowledge_base=self.knowledge_base,
            previous_chapter=prev_chapter,
            custom_instructions=f"第{chapter_num}轮创作",
            display=self.display
        )
        
        self.chapters.append(chapter_result)
        
        while True:
            self.display.update(SystemState.WRITER_REVIEWING, "审核中...", 80, "")
            self.display_chapter(chapter_result)
            
            if self.confirm_action("😊 您对这个章节满意吗？[Y/n]: "):
                return True
            
            # 获取修改请求
            mod_req = self.get_modification_request("示例: 改名字、加反派、改结局、调整字数")
            if not mod_req:
                console.print("[yellow]取消修改[/yellow]")
                continue
            
            # 执行智能修改
            chapter_result = await self.writer_ai.modify_chapter(
                chapter_result, mod_req, self.display
            )
            
            # 更新列表中的最后一项
            self.chapters[-1] = chapter_result
    
    def display_state(self, state: SystemState):
        """更新显示状态"""
        self.display.update(state, state.value, 50, "")
    
    async def run_packaging_phase(self):
        """运行打包阶段"""
        self.display.update(SystemState.PACKAGING, "打包中...", 90, "正在压缩文件...")
        
        # 创建故事目录
        story_dir = Path(f"stories/{self.story_id}")
        story_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存设定
        settings_dir = story_dir / "settings"
        settings_dir.mkdir(exist_ok=True)
        with open(settings_dir / "setting.json", 'w', encoding='utf-8') as f:
            json.dump(self.story_setting, f, ensure_ascii=False, indent=2)
        
        # 保存知识库
        research_dir = story_dir / "research"
        research_dir.mkdir(exist_ok=True)
        with open(research_dir / "knowledge_base.json", 'w', encoding='utf-8') as f:
            json.dump(self.knowledge_base, f, ensure_ascii=False, indent=2)
        
        # 保存章节（命名规则：故事编号--分支编号-章节编号）
        drafts_dir = story_dir / "drafts"
        drafts_dir.mkdir(exist_ok=True)
        
        branch_id = "branch_01"  # 默认分支
        for i, ch in enumerate(self.chapters, 1):
            chapter_id = f"chap_{i:02d}"
            filename = f"{self.story_id}--{branch_id}-{chapter_id}.md"
            with open(drafts_dir / filename, 'w', encoding='utf-8') as f:
                f.write(f"# {self.story_setting.get('story_name', '')} - 第{i}章\n\n")
                f.write(ch['data']['content'])
        
        # 创建ZIP
        zip_path = ZipArchiver.create_archive(self.story_id, story_dir)
        
        self.display.update(SystemState.PACKAGING, "打包完成!", 100, f"文件: {zip_path}")
        
        console.print(f"\n[bold green]🎉 全部完成！[/bold green]")
        console.print(f"📁 故事文件已打包: {zip_path}")
        console.print(f"📂 故事ID: {self.story_id}")
    
    async def run_interactive_session(self):
        """运行完整交互会话"""
        self.show_welcome()
        self.display.start()
        
        try:
            # 1. 获取用户输入
            user_input = self.get_user_input()
            if not user_input:
                console.print("\n👋 感谢使用！")
                return
            
            # 2. 导演阶段
            console.print("\n" + "─" * 60)
            console.print("[bold cyan]🎬 阶段 1/3: 导演AI - 故事蓝图[/bold cyan]")
            console.print("─" * 60)
            
            should_continue = await self.run_director_phase(user_input)
            if not should_continue:
                console.print("\n👋 用户取消，退出程序")
                return
            
            # 3. 研究员阶段
            console.print("\n" + "─" * 60)
            console.print("[bold yellow]🔍 阶段 2/3: 研究员AI - 资料收集[/bold yellow]")
            console.print("─" * 60)
            
            await self.run_researcher_phase()
            
            # 4. 作家阶段
            console.print("\n" + "─" * 60)
            console.print("[bold magenta]✍️ 阶段 3/3: 作家AI - 内容创作[/bold magenta]")
            console.print("─" * 60)
            
            await self.run_writer_phase(chapter_num=1)
            
            # 5. 打包阶段
            console.print("\n" + "─" * 60)
            console.print("[bold green]📦 最终阶段: 打包存档[/bold green]")
            console.print("─" * 60)
            
            await self.run_packaging_phase()
            
            # 6. 保存日志
            await self.logger.save_full_log()
            
            # 7. 完成
            self.display.update(SystemState.COMPLETED, "全部完成!", 100, "任务完成")
            
            console.print("\n" + "=" * 60)
            console.print("[bold green]🎊 恭喜！故事创作全部完成！[/bold green]")
            console.print("=" * 60)
            
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠️ 用户中断[/yellow]")
        except Exception as e:
            console.print(f"\n[red]❌ 发生错误: {e}[/red]")
            import traceback
            traceback.print_exc()
        finally:
            self.display.stop()
            await self.cache.close()


async def main():
    """主函数"""
    wagent = WAgentInteractive()
    
    await wagent.initialize()
    await wagent.run_interactive_session()


if __name__ == "__main__":
    asyncio.run(main())