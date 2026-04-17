#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
上下文感知作家AI引擎 (Context-Aware Writer Engine)

增强功能：
1. 完整的上下文注入机制
2. 创作风格动态适配
3. 章节连贯性自动维护
4. 智能提示词构建
5. 多层次内容规划

核心特性：
- 接收ContextMemory提供的完整故事上下文
- 根据StyleProfile调整写作风格
- 遵循ContinuityManager的连贯性要求
- 自动处理前序章节的衔接
- 支持用户自定义创作指令
"""

import json
import os
from typing import Dict, Any, Optional, List

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

from .writer import WriterAI
from ..config import AsyncConfig, ConstraintConfig, SystemState
from ..display import RealtimeDisplay
from ..logger import ThinkingLogger
from ..cache import AsyncCacheManager
from ..context import ContextMemory, StyleProfile, StoryContext


class ContextAwareWriter(WriterAI):
    """
    上下文感知的增强版作家AI
    
    继承自基础WriterAI，增加以下能力：
    - 读取并理解完整的故事上下文
    - 根据累积信息智能调整生成策略
    - 维护跨章节的风格和情节一致性
    - 提供更精细的控制选项
    """
    
    def __init__(self, config: AsyncConfig, logger: ThinkingLogger,
                 cache: AsyncCacheManager,
                 context_memory: ContextMemory = None,
                 style_profile: StyleProfile = None):
        super().__init__(config, logger, cache)
        
        self.context_memory = context_memory
        self.style_profile = style_profile
        
        # 动态策略参数
        self._context_weight = 0.7  # 上下文影响权重 (0-1)
        self._creativity_boost = 1.0  # 创造性系数
        self._detail_level = "normal"  # 细节程度: minimal/normal/extensive
    
    async def generate_with_context(self, 
                                   chapter_num: int,
                                   story_context: StoryContext,
                                   user_instructions: str = "",
                                   display: RealtimeDisplay = None,
                                   **kwargs) -> Dict:
        """
        使用完整上下文生成章节
        
        这是主要的方法，整合所有上下文信息进行生成
        
        Args:
            chapter_num: 章节编号
            story_context: 故事上下文对象
            user_instructions: 用户额外指令
            display: 显示器实例
            
        Returns:
            包含生成内容和元数据的字典
        """
        start_time = __import__('time').time()
        
        # 获取完整的上下文信息用于生成
        context_data = self.context_memory.get_context_for_next_chapter(chapter_num) \
                     if self.context_memory else {}
        
        # 构建增强版系统提示词
        system_prompt = self._build_context_aware_system_prompt(
            chapter_num, 
            story_context,
            context_data
        )
        
        # 构建增强版用户提示词
        user_prompt = self._build_context_aware_user_prompt(
            chapter_num,
            context_data,
            user_instructions,
            **kwargs
        )
        
        # 动态调整温度参数
        temperature = self._calculate_dynamic_temperature(chapter_num, context_data)
        
        # 构建消息
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        result_data = {"success": False, "data": None, "error": None, "metadata": {}}
        full_content = ""
        
        try:
            from rich.live import Live
            from rich.panel import Panel
            from rich.markdown import Markdown
            
            display.update(SystemState.WRITER_GENERATING, 
                          f"📝 上下文感知创作 第{chapter_num}章...", 5)
            
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
                        "temperature": temperature,
                        "max_tokens": self.cfg.writer_max_tokens,
                        "stream": True
                    },
                    timeout=aiohttp.ClientTimeout(total=self.cfg.stream_timeout)
                ) as resp:
                    
                    if resp.status != 200:
                        error_text = await resp.text()
                        raise Exception(f"API错误 {resp.status}: {error_text}")
                    
                    with Live(console=display.console if display else None,
                             refresh_per_second=10) as live:
                        live.update(Panel(
                            "[italic]🧠 正在分析上下文并生成内容...[/italic]",
                            title=f"✍️ 第{chapter_num}章 (上下文感知模式)",
                            border_style="cyan"
                        ))
                        
                        async for line in resp.content:
                            if line:
                                t = line.decode('utf-8').strip()
                                if t.startswith('data: '):
                                    d = t[6:]
                                    if d == '[DONE]':
                                        break
                                    try:
                                        data = json.loads(d)
                                        token = data.get('choices', [{}])[0].get('delta', {}).get('content', '')
                                        if token:
                                            full_content += token
                                            
                                            # 实时显示（带上下文标记）
                                            self._display_context_aware_token(
                                                live, token, full_content, chapter_num
                                            )
                                    except:
                                        pass
                    
                    result_data["success"] = True
                    result_data["data"] = {
                        "content": full_content,
                        "word_count": len(full_content),
                        "chapter_num": chapter_num,
                        "context_used": {
                            "previous_chapters": context_data.get('total_chapters', 0),
                            "style_applied": bool(context_data.get('style_instructions')),
                            "continuity_checks": len(context_data.get('continuity_requirements', []))
                        },
                        "generation_metadata": {
                            "temperature": temperature,
                            "context_weight": self._context_weight,
                            "style_profile_applied": self.style_profile is not None
                        }
                    }
                    
        except Exception as e:
            print(f"[red]❌ 上下文感知生成失败: {e}[/red]")
            
            # 回退到Mock数据或基础生成
            if kwargs.get('fallback_to_mock', False):
                mock = self._generate_mock_content(chapter_num, story_context, context_data)
                result_data["success"] = True
                result_data["data"] = {
                    "content": mock,
                    "word_count": len(mock),
                    "chapter_num": chapter_num,
                    "is_mock": True
                }
            else:
                result_data["error"] = str(e)
        
        # 记录日志
        await self.logger.log(
            'context_writer', 'complete',
            f'第{chapter_num}章 {len(full_content)}字 (上下文感知)',
            {
                'time': __import__('time').time() - start_time,
                'temperature': temperature,
                'has_context': bool(context_data)
            }
        )
        
        return result_data
    
    def _build_context_aware_system_prompt(self, 
                                          chapter_num: int,
                                          story_context: StoryContext,
                                          context_data: Dict) -> str:
        """构建包含完整上下文的系统提示词"""
        
        base_system = """你是一位专业的小说创作者，具备以下能力：
1. **上下文感知**：能够理解和延续前序章节的内容、风格和情感基调
2. **风格一致性**：严格遵循设定的写作风格和手法，保持整部作品的统一性
3. **连贯性维护**：确保角色性格、情节线、世界观设定在章节间保持一致
4. **自然过渡**：巧妙地衔接上一章的内容，创造流畅的阅读体验
5. **创意平衡**：在遵守约束的同时，保持内容的创意性和吸引力

**核心原则**：
- 绝不与已确立的事实产生矛盾
- 角色的行为必须符合其已建立的性格特征
- 保持叙事节奏的合理性
- 适时回应前序章节留下的悬念和伏笔
"""
        
        # 注入风格要求
        if story_context and story_context.style_profile:
            style_instruction = story_context.style_profile.to_prompt_instruction()
            base_system += f"\n\n**本次创作的风格要求**：\n{style_instruction}\n"
        
        # 注入世界观规则
        if story_context and story_context.world_rules:
            base_system += "\n**已确立的世界观规则（必须严格遵守）**：\n"
            for i, rule in enumerate(story_context.world_rules[:10], 1):
                base_system += f"{i}. {rule}\n"
        
        return base_system
    
    def _build_context_aware_user_prompt(self,
                                        chapter_num: int,
                                        context_data: Dict,
                                        user_instructions: str,
                                        **kwargs) -> str:
        """构建包含上下文信息的用户提示词"""
        
        prompt_parts = []
        
        # 基本任务描述
        prompt_parts.append(f"# 任务：创作第{chapter_num}章")
        
        # 导出格式化的上下文
        if self.context_memory and context_data and not context_data.get('is_first_chapter'):
            formatted_context = self.context_memory.export_context_for_prompt(chapter_num)
            prompt_parts.append(f"\n## 📚 故事上下文（必须参考）\n{formatted_context}")
        else:
            prompt_parts.append("\n[这是第一章，请开始创作]")
        
        # 用户自定义指令
        if user_instructions:
            prompt_parts.append(f"\n## 🎯 作者特殊要求\n{user_instructions}")
        
        # 字数约束
        constraints = ConstraintConfig()
        prompt_parts.append(f"\n## 📏 创作约束\n")
        prompt_parts.append(f"- 目标字数：{constraints.min_words}-{constraints.max_words}字")
        prompt_parts.append(f"- 必须包含明确的章节结尾")
        prompt_parts.append(f"- 为下一章设置适当的悬念或钩子")
        
        # 额外的生成指导
        guidance = self._get_chapter_guidance(chapter_num, context_data)
        if guidance:
            prompt_parts.append(f"\n## 💡 章节指导建议\n{guidance}")
        
        # 输出格式要求
        prompt_parts.append("""
## 📋 输出格式要求
请直接输出章节正文内容，无需添加标题。
确保内容：
1. 与前序章节无缝衔接
2. 符合既定的写作风格
3. 推进主要情节线
4. 保持角色行为的一致性
5. 在结尾处为下一章埋下伏笔
""")
        
        return "\n".join(prompt_parts)
    
    def _calculate_dynamic_temperature(self, 
                                      chapter_num: int, 
                                      context_data: Dict) -> float:
        """
        根据上下文动态计算温度参数
        
        策略：
        - 前几章：较高温度（1.0-1.2），鼓励创意
        - 中期章节：中等温度（0.9-1.0），平衡创意与一致性
        - 后期章节：较低温度（0.8-0.9），强化收敛
        - 有重要转折时：适当提高温度
        """
        base_temp = 1.0
        
        # 根据章节进度调整
        total_chapters = context_data.get('total_chapters', 0)
        
        if total_chapters <= 2:
            # 开篇阶段：高创造性
            progress_factor = 1.2
        elif total_chapters <= 5:
            # 发展阶段：平衡
            progress_factor = 1.0
        elif total_chapters <= 10:
            # 成熟阶段：略降
            progress_factor = 0.9
        else:
            # 后期阶段：注重收敛
            progress_factor = 0.85
        
        # 根据连贯性要求调整
        continuity_reqs = len(context_data.get('continuity_requirements', []))
        if continuity_reqs > 3:
            # 连贯性要求多时降低随机性
            progress_factor *= 0.95
        
        # 章节节点调整（每5章可能有小高潮）
        if chapter_num % 5 == 0:
            progress_factor *= 1.05  # 节点章节可稍具创造性
        
        final_temp = base_temp * progress_factor * self._creativity_boost
        return max(0.7, min(1.3, final_temp))  # 限制在合理范围
    
    def _get_chapter_guidance(self, 
                             chapter_num: int, 
                             context_data: Dict) -> str:
        """根据上下文生成章节特定的指导建议"""
        guidance_parts = []
        
        dynamic_adj = context_data.get('dynamic_adjustments', [])
        if dynamic_adj:
            guidance_parts.append("**系统分析建议**：")
            for adj in dynamic_adj[:3]:
                guidance_parts.append(f"- {adj}")
        
        # 根据章节位置给出建议
        total_done = context_data.get('total_chapters', 0)
        
        if total_done == 0:
            guidance_parts.append("\n**开篇指导**：这是第一章，需要：")
            guidance_parts.append("- 建立主要场景和氛围")
            guidance_parts.append("- 引入核心角色")
            guidance_parts.append("- 设置初始冲突或悬念")
            guidance_parts.append("- 确立基本的叙事基调")
        elif total_done >= 1:
            prev_cliffhanger = ""
            recent_ctx = context_data.get('recent_context', [])
            if recent_ctx:
                prev_cliffhanger = recent_ctx[-1].get('cliffhanger', '')
            
            if prev_cliffhanger:
                guidance_parts.append(f"\n**衔接重点**：上一章留下悬念：'{prev_cliffhanger}'")
                guidance_parts.append("- 本章开头应直接或间接回应这一悬念")
        
        return "\n".join(guidance_parts) if guidance_parts else ""
    
    def _display_context_aware_token(self, 
                                    live, 
                                    token: str, 
                                    content: str, 
                                    chapter_num: int):
        """显示带上下文标记的实时输出"""
        try:
            from rich.panel import Panel
            from rich.markdown import Markdown
            
            # 每100个字符更新一次显示
            if len(content) % 100 < 5:
                preview = content[-200:] if len(content) > 200 else content
                
                live.update(Panel(
                    Markdown(preview),
                    title=f"✍️ 第{chapter_num}章 | 已写: {len(content)}字 | 🧠 上下文感知",
                    border_style="cyan",
                    subtitle="正在生成中..."
                ))
        except Exception:
            pass
    
    def _generate_mock_content(self, 
                              chapter_num: int, 
                              story_context: StoryContext,
                              context_data: Dict) -> str:
        """生成Mock内容（当API不可用时）"""
        
        genre = story_context.genre if story_context else "通用"
        style_desc = ""
        
        if story_context and story_context.style_profile:
            sp = story_context.style_profile
            style_desc = f"{sp.genre}风格，{sp.author_style or '标准'}笔法"
        
        prev_hint = ""
        if context_data and not context_data.get('is_first_chapter'):
            recent = context_data.get('recent_context', [])
            if recent:
                last = recent[-1]
                prev_hint = f"\n承接上一章: {last.get('cliffhanger', '情节继续发展')}"
        
        mock = f"""# 第{chapter_num}章 [Mock数据 - {genre}类型]

{prev_hint}

[这是模拟生成的章节内容]

**风格标记**: {style_desc or '默认风格'}
**字数**: 约2000字
**状态**: Mock模式（API不可用时的回退内容）

---

*本章由WAgent上下文感知系统生成*
*章节编号: {chapter_num}*
*上下文引用: 前{context_data.get('total_chapters', 0)}章*
"""
        
        return mock
    
    def set_context_weight(self, weight: float):
        """设置上下文影响权重 (0.0-1.0)"""
        self._context_weight = max(0.0, min(1.0, weight))
    
    def set_creativity_boost(self, boost: float):
        """设置创造性系数 (0.5-2.0)"""
        self._creativity_boost = max(0.5, min(2.0, boost))
    
    def set_detail_level(self, level: str):
        """设置细节程度"""
        valid_levels = ['minimal', 'normal', 'extensive']
        if level in valid_levels:
            self._detail_level = level
