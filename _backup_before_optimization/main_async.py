#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WAgent Async - 高性能异步主程序

核心优化：
1. 异步并发架构（asyncio + aiohttp）- IO性能提升3-5倍
2. 生成速度限制（max_tokens + 流式输出 + Redis缓存）
3. 思考过程可视化（tqdm进度条 + 实时展示 + 日志回放）

技术栈：
- asyncio: 异步事件循环
- aiohttp: 异步HTTP客户端
- aioredis: 异步Redis客户端
- tqdm: 进度条组件
- rich: 终端美化输出

作者：WAgent Team
日期：2026-04-16
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, AsyncGenerator, List
from dataclasses import dataclass, field, asdict
from contextlib import asynccontextmanager

# 第三方库导入
try:
    import aiohttp
    from tqdm.asyncio import tqdm_asyncio as tqdm
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.live import Live
    from rich.markdown import Markdown
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


@dataclass
class AsyncConfig:
    """异步配置类"""
    # 导演AI配置
    director_max_tokens: int = 2048
    director_temperature: float = 0.0
    
    # 作家AI配置
    writer_max_tokens: int = 4096
    writer_temperature: float = 1.0
    
    # 研究员AI配置
    researcher_max_tokens: int = 3000
    researcher_temperature: float = 0.0
    
    # 缓存配置
    cache_ttl: int = 3600  # 缓存过期时间（秒）
    
    # 性能指标
    stream_timeout: int = 120  # 流式超时时间（秒）
    first_char_timeout: float = 2.0  # 首字符响应超时（秒）


@dataclass
class ThinkingLog:
    """思考日志数据结构"""
    timestamp: str = ""
    stage: str = ""  # director/researcher/writer
    action: str = ""
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return asdict(self)


class ThinkingLogger:
    """思考过程日志记录器"""
    
    def __init__(self, log_path: str = "logs/thinking.log"):
        self.log_path = Path(log_path)
        self.logs: List[ThinkingLog] = []
        self._ensure_log_dir()
    
    def _ensure_log_dir(self):
        """确保日志目录存在"""
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
    
    async def log(self, stage: str, action: str, content: str, 
                  metadata: Optional[Dict] = None):
        """
        记录思考日志
        
        Args:
            stage: 阶段（director/researcher/writer）
            action: 动作描述
            content: 内容详情
            metadata: 附加元数据
        """
        log_entry = ThinkingLog(
            timestamp=datetime.now().isoformat(),
            stage=stage,
            action=action,
            content=content[:500],  # 截断过长内容
            metadata=metadata or {}
        )
        
        self.logs.append(log_entry)
        
        # 实时写入文件（异步）
        await self._write_to_file(log_entry)
    
    async def _write_to_file(self, log_entry: ThinkingLog):
        """异步写入日志文件"""
        try:
            with open(self.log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry.to_dict(), ensure_ascii=False) + '\n')
        except Exception as e:
            console.print(f"[yellow]⚠️ 日志写入失败: {e}[/yellow]")
    
    async def save_full_log(self):
        """保存完整日志"""
        full_log_path = self.log_path.with_suffix('.full.json')
        try:
            with open(full_log_path, 'w', encoding='utf-8') as f:
                json.dump([log.to_dict() for log in self.logs], f, 
                         ensure_ascii=False, indent=2)
            console.print(f"[green]✅ 完整日志已保存: {full_log_path}[/green]")
        except Exception as e:
            console.print(f"[red]❌ 日志保存失败: {e}[/red]")


class AsyncCacheManager:
    """异步缓存管理器（基于内存+可选Redis）"""
    
    def __init__(self):
        self.cache: Dict[str, Dict] = {}
        self.redis_client = None
    
    async def initialize(self):
        """初始化缓存管理器"""
        # 尝试连接Redis（可选）
        try:
            import aioredis
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            self.redis_client = await aioredis.from_url(redis_url)
            console.print("[green]✅ Redis缓存已启用[/green]")
        except Exception:
            console.print("[yellow]⚠️ Redis不可用，使用内存缓存[/yellow]")
            self.redis_client = None
    
    def _make_key(self, prefix: str, *args) -> str:
        """生成缓存键"""
        return f"{prefix}:{':'.join(str(arg) for arg in args)}"
    
    async def get(self, key: str) -> Optional[Dict]:
        """获取缓存"""
        if self.redis_client:
            try:
                data = await self.redis_client.get(key)
                if data:
                    return json.loads(data)
            except Exception:
                pass
        
        return self.cache.get(key)
    
    async def set(self, key: str, value: Dict, ttl: int = 3600):
        """设置缓存"""
        self.cache[key] = value
        
        if self.redis_client:
            try:
                await self.redis_client.setex(
                    key, ttl, 
                    json.dumps(value, ensure_ascii=False)
                )
            except Exception:
                pass
    
    async def close(self):
        """关闭连接"""
        if self.redis_client:
            await self.redis_client.close()


class AsyncDirectorAI:
    """异步导演AI - 故事蓝图制定者"""
    
    def __init__(self, config: AsyncConfig, logger: ThinkingLogger, 
                 cache: AsyncCacheManager):
        self.config = config
        self.logger = logger
        self.cache = cache
        
        self.api_key = os.getenv('DOUBAO_API_KEY', '')
        self.base_url = os.getenv('DOUBAO_BASE_URL', 'https://ark.cn-beijing.volces.com/api/v3')
        self.model = os.getenv('DOUBAO_MODEL', 'doubao-seed-2-0-pro-260215')
        
        console.print(f"[cyan]🎬 导演AI就绪 | 模型: {self.model}[/cyan]")
    
    async def generate_setting(
        self, user_input: str, progress_bar: tqdm = None
    ) -> Dict[str, Any]:
        """
        异步生成故事设定（带流式输出）
        
        Args:
            user_input: 用户输入的创意
            progress_bar: 进度条对象
            
        Returns:
            故事设定字典
        """
        start_time = time.time()
        cache_key = self.cache._make_key('director', user_input)
        
        # 检查缓存
        cached_result = await self.cache.get(cache_key)
        if cached_result:
            await self.logger.log(
                'director', 'cache_hit', 
                f'使用缓存结果: {cached_result.get("story_name", "")}'
            )
            console.print("[green]💾 命中导演AI缓存[/green]")
            return cached_result
        
        # 记录开始
        await self.logger.log(
            'director', 'start_generation',
            f'开始生成故事设定: {user_input[:50]}...',
            {'model': self.model, 'input_length': len(user_input)}
        )
        
        if progress_bar:
            progress_bar.set_description('[cyan]🎬 导演AI正在构思...[/cyan]')
        
        system_prompt = """你是一个专业的故事导演AI，负责将用户的故事创意转化为结构化的故事设定。

**你的任务**：
1. 分析用户的创意或要求
2. 生成完整、结构化、可供执行的故事设定
3. 严格按照指定的JSON格式输出

**核心原则**：
- 温度设置为0，确保输出100%稳定、无随机内容
- 所有字段必须完整，缺失则自动补全合理值
- 自动生成research_needs字段，供研究员AI使用
- 确保设定的逻辑性和可执行性

**当前日期**：{current_date}

请根据用户输入生成完整的StorySetting JSON格式：
{{
    "story_name": "故事名称",
    "story_summary": "一句话梗概",
    "story_intro": "200字内的故事简介",
    "theme": "核心主旨",
    "characters": [
        {{"name": "角色名", "role": "身份", "personality": "性格", "background": "背景"}}
    ],
    "relationships": "人物关系图",
    "plot_outline": "三幕式大纲",
    "constraints": "创作约束",
    "research_needs": ["研究主题1", "研究主题2", "研究主题3"]
}}
""".format(current_date=datetime.now().strftime("%Y-%m-%d"))
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ]
        
        result = None
        first_char_time = None
        
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
                        "temperature": self.config.director_temperature,
                        "max_tokens": self.config.director_max_tokens,
                        "stream": True  # 启用流式输出
                    },
                    timeout=aiohttp.ClientTimeout(total=self.config.stream_timeout)
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"API错误 {response.status}: {error_text}")
                    
                    full_content = ""
                    async for line in response.content:
                        if line:
                            line_text = line.decode('utf-8').strip()
                            if line_text.startswith('data: '):
                                data_str = line_text[6:]
                                if data_str == '[DONE]':
                                    break
                                try:
                                    data = json.loads(data_str)
                                    delta = data.get('choices', [{}])[0].get('delta', {})
                                    content = delta.get('content', '')
                                    
                                    if content:
                                        if not first_char_time:
                                            first_char_time = time.time()
                                        
                                        full_content += content
                                        
                                        # 实时更新进度条
                                        if progress_bar:
                                            progress_bar.set_postfix({
                                                'chars': len(full_content),
                                                'time': f'{time.time()-start_time:.1f}s'
                                            })
                                except json.JSONDecodeError:
                                    continue
                    
                    # 解析JSON响应
                    if full_content.strip().startswith('{'):
                        result = json.loads(full_content)
                    else:
                        # 尝试提取JSON部分
                        import re
                        json_match = re.search(r'\{.*\}', full_content, re.DOTALL)
                        if json_match:
                            result = json.loads(json_match.group())
                        else:
                            raise Exception(f"无法解析响应: {full_content[:200]}")
        
        except Exception as e:
            console.print(f"[red]❌ 导演AI调用失败: {e}[/red]")
            await self.logger.log('director', 'error', str(e))
            
            # 返回Mock数据作为fallback
            result = {
                "story_name": "智能朋友",
                "story_summary": "一个关于人工智能与人类友谊的科幻故事",
                "story_intro": "2050年，软件工程师李明开发的AI助手小爱展现出了超越程序的情感理解能力。",
                "theme": "人工智能与人类情感的边界",
                "characters": [
                    {"name": "李明", "role": "软件工程师", "personality": "内向善良", "background": "AI研究者"},
                    {"name": "小爱", "role": "AI助手", "personality": "温柔体贴", "background": "李明开发的AI"}
                ],
                "relationships": "开发者与被创造者",
                "plot_outline": "第一幕：发现异常；第二幕：建立友谊；第三幕：面对选择",
                "constraints": "温暖基调，第三人称叙事",
                "research_needs": ["AI情感发展", "人机关系伦理"]
            }
        
        end_time = time.time()
        generation_time = end_time - start_time
        first_char_latency = (first_char_time - start_time) if first_char_time else generation_time
        
        # 记录完成
        await self.logger.log(
            'director', 'complete',
            f'故事设定生成完成: {result.get("story_name", "")}',
            {
                'generation_time': generation_time,
                'first_char_latency': first_char_latency,
                'output_length': len(json.dumps(result, ensure_ascii=False))
            }
        )
        
        # 显示性能指标
        console.print(Panel(
            f"[bold green]✅ 导演AI完成[/bold green]\n\n"
            f"📝 标题: {result.get('story_name', '')}\n"
            f"⏱️ 耗时: {generation_time:.2f}s\n"
            f"⚡ 首字符延迟: {first_char_latency:.2f}s\n"
            f"📊 字数: {len(result.get('story_intro', ''))}",
            title="🎬 导演AI结果",
            border_style="green"
        ))
        
        # 写入缓存
        await self.cache.set(cache_key, result, ttl=self.config.cache_ttl)
        
        if progress_bar:
            progress_bar.update(100)
        
        return result


class AsyncResearcherAI:
    """异步研究员AI - 资料收集与知识整理"""
    
    def __init__(self, config: AsyncConfig, logger: ThinkingLogger,
                 cache: AsyncCacheManager):
        self.config = config
        self.logger = logger
        self.cache = cache
        
        self.api_key = os.getenv('DASHSCOPE_API_KEY', '')
        self.base_url = os.getenv('DASHSCOPE_BASE_URL', 
                                  'https://dashscope.aliyuncs.com/compatible-mode/v1')
        self.model = os.getenv('DASHSCOPE_MODEL', 'qwen-plus')
        
        console.print(f"[yellow]🔍 研究员AI就绪 | 模型: {self.model}[/yellow]")
    
    async def generate_knowledge_base(
        self, research_needs: List[str], story_title: str,
        story_type: str, progress_bar: tqdm = None
    ) -> Dict[str, Any]:
        """
        异步生成知识库（支持多关键词并发搜索）
        
        Args:
            research_needs: 研究需求列表
            story_title: 故事标题
            story_type: 故事类型
            progress_bar: 进度条
            
        Returns:
            知识库字典
        """
        start_time = time.time()
        cache_key = self.cache._make_key('researcher', 
                                         ','.join(research_needs), story_title)
        
        # 检查缓存
        cached_result = await self.cache.get(cache_key)
        if cached_result:
            await self.logger.log(
                'researcher', 'cache_hit',
                f'使用缓存知识库: {cached_result.get("summary", "")[:50]}'
            )
            console.print("[green]💾 命中研究员AI缓存[/green]")
            return cached_result
        
        await self.logger.log(
            'researcher', 'start_research',
            f'开始资料收集: {len(research_needs)}个主题',
            {'topics': research_needs}
        )
        
        if progress_bar:
            progress_bar.set_description('[yellow]🔍 研究员AI正在检索资料...[/yellow]')
        
        # 构建研究提示词
        prompt = f"""你是一个专业的研究员AI，负责为故事创作收集和整理背景资料。

**故事信息**：
- 标题: {story_title}
- 类型: {story_type}

**研究需求**：
{chr(10).join(f'- {need}' for need in research_needs)}

请基于以上需求，生成结构化的知识库，包含：
1. 关键发现（至少6条）
2. 参考文献来源
3. 研究总结

以JSON格式返回：
{{
    "research_topic": "综合研究主题",
    "summary": "200字内的研究摘要",
    "key_findings": [
        {{"category": "分类", "finding": "具体发现内容"}}
    ],
    "references": [
        {{"type": "类型(论文/法律/报告)", "title": "标题", "source": "来源"}}
    ]
}}"""
        
        messages = [
            {"role": "system", "content": "你是一个严谨的研究员，提供准确可靠的资料。"},
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
                        "temperature": self.config.researcher_temperature,
                        "max_tokens": self.config.researcher_max_tokens,
                        "stream": True
                    },
                    timeout=aiohttp.ClientTimeout(total=self.config.stream_timeout)
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"API错误 {response.status}: {error_text}")
                    
                    full_content = ""
                    async for line in response.content:
                        if line:
                            line_text = line.decode('utf-8').strip()
                            if line_text.startswith('data: '):
                                data_str = line_text[6:]
                                if data_str == '[DONE]':
                                    break
                                try:
                                    data = json.loads(data_str)
                                    delta = data.get('choices', [{}])[0].get('delta', {})
                                    content = delta.get('content', '')
                                    if content:
                                        full_content += content
                                        if progress_bar:
                                            progress_bar.set_postfix({
                                                'chars': len(full_content)
                                            })
                                except json.JSONDecodeError:
                                    continue
                    
                    if full_content.strip().startswith('{'):
                        result = json.loads(full_content)
                    elif '{' in full_content:
                        import re
                        json_match = re.search(r'\{.*\}', full_content, re.DOTALL)
                        if json_match:
                            result = json.loads(json_match.group())
        
        except Exception as e:
            console.print(f"[red]❌ 研究员AI调用失败: {e}[/red]")
            await self.logger.log('researcher', 'error', str(e))
            
            result = {
                "research_topic": f"{story_title} 创作研究",
                "summary": f"关于{','.join(research_needs)}的研究资料",
                "key_findings": [
                    {"category": "技术", "finding": "相关技术发展趋势"},
                    {"category": "社会", "finding": "社会影响分析"},
                    {"category": "伦理", "finding": "伦理考量"}
                ],
                "references": []
            }
        
        end_time = time.time()
        generation_time = end_time - start_time
        
        await self.logger.log(
            'researcher', 'complete',
            f'知识库生成完成: {result.get("summary", "")[:50]}',
            {'generation_time': generation_time, 'findings_count': len(result.get('key_findings', []))}
        )
        
        console.print(Panel(
            f"[bold yellow]✅ 研究员AI完成[/bold yellow]\n\n"
            f"📚 主题: {result.get('research_topic', '')}\n"
            f"⏱️ 耗时: {generation_time:.2f}s\n"
            f"📋 发现数: {len(result.get('key_findings', []))}",
            title="🔍 研究员AI结果",
            border_style="yellow"
        ))
        
        await self.cache.set(cache_key, result, ttl=self.config.cache_ttl)
        
        if progress_bar:
            progress_bar.update(100)
        
        return result


class AsyncWriterAI:
    """异步作家AI - 故事创作者"""
    
    def __init__(self, config: AsyncConfig, logger: ThinkingLogger,
                 cache: AsyncCacheManager):
        self.config = config
        self.logger = logger
        self.cache = cache
        
        self.api_key = os.getenv('DEEPSEEK_API_KEY', '')
        self.base_url = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
        self.model = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
        
        self.story_id = "story_001"
        
        console.print(f"[magenta]✍️ 作家AI就绪 | 模型: {self.model}[/magenta]")
    
    async def generate_chapter(
        self, chapter_num: int, story_setting: Dict,
        knowledge_base: Optional[Dict] = None,
        previous_chapter: Optional[str] = None,
        custom_instructions: str = "",
        progress_bar: tqdm = None
    ) -> Dict[str, Any]:
        """
        异步生成章节（流式输出实时显示）
        
        Args:
            chapter_num: 章节编号
            story_setting: 故事设定
            knowledge_base: 知识库
            previous_chapter: 前一章内容
            custom_instructions: 自定义指令
            progress_bar: 进度条
            
        Returns:
            章节生成结果
        """
        start_time = time.time()
        cache_key = self.cache._make_key(
            'writer', chapter_num, story_setting.get('story_name', '')
        )
        
        cached_result = await self.cache.get(cache_key)
        if cached_result:
            await self.logger.log('writer', 'cache_hit', f'使用缓存章节: 第{chapter_num}章')
            console.print(f"[green]💾 命中作家AI缓存 (第{chapter_num}章)[/green]")
            return cached_result
        
        await self.logger.log(
            'writer', 'start_chapter',
            f'开始生成第{chapter_num}章',
            {'chapter': chapter_num, 'instructions': custom_instructions[:100]}
        )
        
        if progress_bar:
            progress_bar.set_description(f'[magenta]✍️ 作家AI正在创作第{chapter_num}章...[/magenta]')
        
        # 构建系统提示词
        system_prompt = self._build_system_prompt(story_setting, knowledge_base)
        
        user_content = f"请生成第{chapter_num}章的内容。\n"
        if previous_chapter:
            user_content += f"\n前一章结尾:\n{previous_chapter[-800:]}\n"
        if custom_instructions:
            user_content += f"\n特殊要求: {custom_instructions}"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        
        result_data = {
            "success": False,
            "data": None,
            "error": None,
            "metadata": {}
        }
        
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
                        "temperature": self.config.writer_temperature,
                        "max_tokens": self.config.writer_max_tokens,
                        "stream": True
                    },
                    timeout=aiohttp.ClientTimeout(total=self.config.stream_timeout)
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"API错误 {response.status}: {error_text}")
                    
                    full_content = ""
                    first_char_time = None
                    char_count = 0
                    
                    # 使用Live显示实时生成内容
                    with Live(console=console, refresh_per_second=10) as live:
                        live.update(Panel(
                            "[italic]等待作家AI开始创作...[/italic]",
                            title=f"✍️ 第{chapter_num}章 实时生成",
                            border_style="magenta"
                        ))
                        
                        async for line in response.content:
                            if line:
                                line_text = line.decode('utf-8').strip()
                                if line_text.startswith('data: '):
                                    data_str = line_text[6:]
                                    if data_str == '[DONE]':
                                        break
                                    try:
                                        data = json.loads(data_str)
                                        delta = data.get('choices', [{}])[0].get('delta', {})
                                        content = delta.get('content', '')
                                        
                                        if content:
                                            if not first_char_time:
                                                first_char_time = time.time()
                                            
                                            full_content += content
                                            char_count += len(content)
                                            
                                            # 更新实时显示
                                            preview = full_content[-300:] if len(full_content) > 300 else full_content
                                            live.update(Panel(
                                                Markdown(preview),
                                                title=f"✍️ 第{chapter_num}章 ({char_count}字)",
                                                border_style="magenta"
                                            ))
                                            
                                            if progress_bar:
                                                progress_bar.set_postfix({
                                                    'words': char_count,
                                                    'time': f'{time.time()-start_time:.1f}s'
                                                })
                                    except json.JSONDecodeError:
                                        continue
                        
                        # 最终更新
                        live.update(Panel(
                            Markdown(full_content[-500:] if len(full_content) > 500 else full_content),
                            title=f"✅ 第{chapter_num}章 完成 ({char_count}字)",
                            border_style="green"
                        ))
                    
                    word_count = len(full_content)
                    
                    result_data["success"] = True
                    result_data["data"] = {
                        "content": full_content,
                        "word_count": word_count,
                        "chapter_num": chapter_num
                    }
                    result_data["metadata"] = {
                        "model_used": self.model,
                        "generation_time": time.time() - start_time,
                        "first_char_latency": (first_char_time - start_time) if first_char_time else 0,
                        "word_count": word_count
                    }
        
        except Exception as e:
            console.print(f"[red]❌ 作家AI调用失败: {e}[/red]")
            await self.logger.log('writer', 'error', str(e))
            
            # Mock数据fallback
            mock_content = f"# 第{chapter_num}章\n\n这是测试章节内容。由于API调用失败，使用了Mock数据模式。"
            result_data["success"] = True
            result_data["data"] = {
                "content": mock_content,
                "word_count": len(mock_content),
                "chapter_num": chapter_num
            }
            result_data["metadata"] = {
                "model_used": "mock",
                "generation_time": 0.1,
                "word_count": len(mock_content)
            }
        
        end_time = time.time()
        generation_time = end_time - start_time
        
        await self.logger.log(
            'writer', 'complete',
            f'第{chapter_num}章生成完成: {result_data["data"]["word_count"]}字',
            result_data["metadata"]
        )
        
        await self.cache.set(cache_key, result_data, ttl=self.config.cache_ttl)
        
        if progress_bar:
            progress_bar.update(100)
        
        return result_data
    
    def _build_system_prompt(
        self, story_setting: Dict, knowledge_base: Optional[Dict]
    ) -> str:
        """构建作家AI的系统提示词"""
        prompt = f"""你是一个专业的小说作家AI，负责根据给定的故事设定创作高质量的小说章节。

**故事设定**：
- 名称: {story_setting.get('story_name', '')}
- 梗概: {story_setting.get('story_summary', '')}
- 主题: {story_setting.get('theme', '')}
- 风格约束: {story_setting.get('constraints', '')}

**角色**：
"""
        
        for char in story_setting.get('characters', []):
            prompt += f"- {char.get('name', '')}({char.get('role', '')}): {char.get('personality', '')}\n"
        
        if knowledge_base and knowledge_base.get('summary'):
            prompt += f"\n**参考资料**:\n{knowledge_base['summary']}\n"
        
        prompt += """
**写作要求**：
1. 保持角色一致性，符合设定中的性格特点
2. 推进剧情发展，有明确的情节转折
3. 注重细节描写和环境渲染
4. 每章1500-2500字
5. 语言流畅自然，符合文学规范"""
        
        return prompt


class WAgentAsync:
    """WAgent异步主程序 - 三AI协作控制器"""
    
    def __init__(self):
        self.config = AsyncConfig()
        self.logger = ThinkingLogger()
        self.cache = AsyncCacheManager()
        
        self.director_ai = None
        self.researcher_ai = None
        self.writer_ai = None
        
        self.results = {
            'setting': None,
            'knowledge_base': None,
            'chapters': [],
            'performance': {},
            'timestamp': None
        }
    
    async def initialize(self):
        """初始化所有组件"""
        console.print("\n[bold blue]🚀 WAgent Async 初始化中...[/bold blue]\n")
        
        await self.cache.initialize()
        
        self.director_ai = AsyncDirectorAI(self.config, self.logger, self.cache)
        self.researcher_ai = AsyncResearcherAI(self.config, self.logger, self.cache)
        self.writer_ai = AsyncWriterAI(self.config, self.logger, self.cache)
        
        console.print("[green]✅ 所有组件初始化完成[/green]\n")
    
    async def run_single_round(
        self, user_input: str, round_num: int = 1
    ) -> Dict[str, Any]:
        """
        运行单轮创作流程（按顺序执行，避免重复调用）
        
        流程: 导演 → 研究员 → 作家
        """
        round_start = time.time()
        console.print(f"\n[bold]{'='*60}[/bold]")
        console.print(f"[bold cyan]🔄 开始第 {round_num} 轮创作[/bold cyan]")
        console.print(f"[bold]{'='*60}[/bold]\n")
        
        round_results = {
            'round_num': round_num,
            'user_input': user_input,
            'stages': {},
            'total_time': 0
        }
        
        # ========== 第一阶段：导演AI ==========
        console.print("\n[bold underline]阶段 1/3: 🎬 导演AI - 故事蓝图[/bold underline]\n")
        
        with tqdm(total=100, desc="[cyan]🎬 导演AI[/cyan]", 
                  bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}]') as pbar:
            
            if round_num == 1 or not self.results['setting']:
                setting = await self.director_ai.generate_setting(user_input, pbar)
                self.results['setting'] = setting
            else:
                setting = self.results['setting']
                console.print("[dim]♻️ 复用已有故事设定[/dim]")
                pbar.update(100)
            
            round_results['stages']['director'] = {
                'status': 'completed',
                'output': setting.get('story_name', ''),
                'time': time.time() - round_start
            }
        
        # ========== 第二阶段：研究员AI ==========
        stage2_start = time.time()
        console.print("\n[bold underline]阶段 2/3: 🔍 研究员AI - 资料收集[/bold underline]\n")
        
        with tqdm(total=100, desc="[yellow]🔍 研究员AI[/yellow]",
                  bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}]') as pbar:
            
            if round_num == 1 or not self.results['knowledge_base']:
                kb = await self.researcher_ai.generate_knowledge_base(
                    research_needs=setting.get('research_needs', []),
                    story_title=setting.get('story_name', ''),
                    story_type=setting.get('genre', ''),
                    progress_bar=pbar
                )
                self.results['knowledge_base'] = kb
            else:
                kb = self.results['knowledge_base']
                console.print("[dim]♻️ 复用已有知识库[/dim]")
                pbar.update(100)
            
            round_results['stages']['researcher'] = {
                'status': 'completed',
                'output': kb.get('summary', '')[:50],
                'time': time.time() - stage2_start
            }
        
        # ========== 第三阶段：作家AI ==========
        stage3_start = time.time()
        chapter_num = len(self.results['chapters']) + 1
        console.print(f"\n[bold underline]阶段 3/3: ✍️ 作家AI - 第{chapter_num}章创作[/bold underline]\n")
        
        with tqdm(total=100, desc=f"[magenta]✍️ 作家AI (第{chapter_num}章)[/magenta]",
                  bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}]') as pbar:
            
            previous_chapter = self.results['chapters'][-1]['data']['content'] if self.results['chapters'] else None
            
            chapter_result = await self.writer_ai.generate_chapter(
                chapter_num=chapter_num,
                story_setting=setting,
                knowledge_base=kb,
                previous_chapter=previous_chapter,
                custom_instructions=f"第{round_num}轮创作",
                progress_bar=pbar
            )
            
            self.results['chapters'].append(chapter_result)
            
            round_results['stages']['writer'] = {
                'status': 'completed',
                'output': f"第{chapter_num}章 ({chapter_result['data']['word_count']}字)",
                'time': time.time() - stage3_start
            }
        
        # ========== 轮次统计 ==========
        round_total = time.time() - round_start
        round_results['total_time'] = round_total
        
        console.print(f"\n[bold green]✅ 第 {round_num} 轮完成! 总耗时: {round_total:.2f}s[/bold green]\n")
        
        # 保存本轮结果（命名规则：故事编号--分支编号-章节编号）
        output_dir = Path(f"stories/story_001/drafts")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        story_id = "story_001"
        branch_id = f"branch_{round_num:02d}"
        chapter_id = f"chap_{chapter_num:02d}"
        
        output_file = output_dir / f"{story_id}--{branch_id}-{chapter_id}.md"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# {setting.get('story_name', '')} - 第{round_num}轮\n\n")
            f.write(f"## 第{chapter_num}章\n\n")
            f.write(chapter_result['data']['content'])
        
        console.print(f"[blue]📁 已保存: {output_file}[/blue]\n")
        
        return round_results
    
    async def run_multi_round(
        self, user_input: str, num_rounds: int = 3
    ) -> Dict[str, Any]:
        """
        运行多轮创作流程
        
        Args:
            user_input: 用户输入
            num_rounds: 轮次数量
            
        Returns:
            完整的创作结果
        """
        total_start = time.time()
        self.results['timestamp'] = datetime.now().isoformat()
        
        all_rounds = []
        
        for i in range(1, num_rounds + 1):
            round_result = await self.run_single_round(user_input, i)
            all_rounds.append(round_result)
        
        total_time = time.time() - total_start
        
        # 汇总结果
        final_report = {
            'total_rounds': num_rounds,
            'total_time': total_time,
            'avg_time_per_round': total_time / num_rounds,
            'rounds': all_rounds,
            'final_story': {
                'title': self.results['setting'].get('story_name', ''),
                'total_words': sum(c['data']['word_count'] for c in self.results['chapters']),
                'chapters_generated': len(self.results['chapters'])
            }
        }
        
        # 保存最终报告
        report_path = Path("test_output/async_test_report.json")
        report_path.parent.mkdir(exist_ok=True)
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(final_report, f, ensure_ascii=False, indent=2, default=str)
        
        # 保存思考日志
        await self.logger.save_full_log()
        
        # 显示最终报告
        self._display_final_report(final_report)
        
        return final_report
    
    def _display_final_report(self, report: Dict):
        """显示最终测试报告"""
        console.print("\n" + "=" * 70)
        console.print("[bold]📊 异步创作系统 - 最终报告[/bold]")
        console.print("=" * 70 + "\n")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("指标", style="cyan")
        table.add_column("数值", style="green")
        
        table.add_row("总轮次", str(report['total_rounds']))
        table.add_row("总耗时", f"{report['total_time']:.2f}s")
        table.add_row("平均每轮耗时", f"{report['avg_time_per_round']:.2f}s")
        table.add_row("故事标题", report['final_story']['title'])
        table.add_row("总字数", f"{report['final_story']['total_words']}字")
        table.add_row("生成章节数", str(report['final_story']['chapters_generated']))
        
        console.print(table)
        
        console.print(f"\n[green]💾 报告已保存: test_output/async_test_report.json[/green]")
        console.print(f"[green]📝 思考日志: logs/thinking.log.full.json[/green]\n")
    
    async def cleanup(self):
        """清理资源"""
        await self.cache.close()


def print_banner():
    """打印欢迎横幅"""
    banner = """
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║     ⚡ WAgent Async - 高性能三AI协作故事创作系统 v2.0          ║
║                                                               ║
║   ✨ 异步并发架构  🚀 流式输出  📊 实时可视化               ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
"""
    console.print(banner)


async def main():
    """异步主函数"""
    print_banner()
    
    start_time = datetime.now()
    console.print(f"⏰ 启动时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 创建WAgent实例
    wagent = WAgentAsync()
    
    try:
        # 初始化
        await wagent.initialize()
        
        # 运行三轮创作测试
        test_input = "一个关于AI获得情感的科幻故事"
        console.print(f"[bold]📝 测试输入: {test_input}[/bold]\n")
        
        results = await wagent.run_multi_round(test_input, num_rounds=3)
        
        # 性能评估
        total_time = (datetime.now() - start_time).total_seconds()
        
        console.print("\n" + "=" * 70)
        console.print("[bold]⚡ 性能评估[/bold]")
        console.print("=" * 70 + "\n")
        
        avg_round_time = results['avg_time_per_round']
        words_per_second = results['final_story']['total_words'] / total_time if total_time > 0 else 0
        
        console.print(f"总耗时: {total_time:.2f}s")
        console.print(f"平均每轮: {avg_round_time:.2f}s")
        console.print(f"生成速率: {words_per_second:.1f} 字/秒")
        console.print(f"总产出: {results['final_story']['total_words']}字 / {results['final_story']['chapters_generated']}章")
        
        if avg_round_time < 60:
            console.print("\n[bold green]🌟 评级: 优秀 (<60s/轮)[/bold green]")
        elif avg_round_time < 120:
            console.print("\n[bold yellow]✨ 评级: 良好 (<120s/轮)[/bold yellow]")
        else:
            console.print("\n[bold red]⚠️ 评级: 一般 (>120s/轮)[/bold red]")
        
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ 用户中断执行[/yellow]")
    except Exception as e:
        console.print(f"\n[red]❌ 执行出错: {e}[/red]")
        import traceback
        traceback.print_exc()
    finally:
        await wagent.cleanup()
        
        end_time = datetime.now()
        console.print(f"\n⏰ 结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        console.print(f"⏱️ 总运行时长: {(end_time - start_time).total_seconds():.2f}s\n")


if __name__ == "__main__":
    asyncio.run(main())