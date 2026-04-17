#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
上下文感知记忆系统 (Context-Aware Memory System)

核心功能：
1. 章节级上下文记录与追踪
2. 创作约束条件持久化存储
3. 风格偏好与写作手法记忆
4. 角色状态与情节线管理
5. 上下文摘要自动生成

设计原则：
- 高内聚：所有上下文信息集中管理
- 低耦合：通过标准化接口对外提供数据
- 持久化：支持JSON序列化，跨会话保持
- 可扩展：支持自定义元数据和标签系统
"""

import json
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class ChapterContext:
    """单章节上下文信息"""
    chapter_num: int
    title: str = ""
    content_summary: str = ""  # 内容摘要（用于传递给后续章节）
    word_count: int = 0
    key_events: List[str] = field(default_factory=list)  # 关键事件列表
    character_states: Dict[str, str] = field(default_factory=dict)  # 角色状态变化
    plot_threads: List[str] = field(default_factory=list)  # 情节线索
    emotional_tone: str = ""  # 情感基调
    cliffhanger: str = ""  # 悬念/钩子（连接下一章）
    writing_techniques_used: List[str] = field(default_factory=list)  # 使用的写作手法
    metadata: Dict[str, Any] = field(default_factory=dict)  # 自定义元数据
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class StyleProfile:
    """创作风格配置文件"""
    genre: str = "通用"  # 类型: 悬疑/科幻/浪漫/武侠等
    sub_genre: str = ""  # 子类型
    author_style: str = ""  # 作者风格模仿: 海明威/金庸/村上春树等
    narrative_voice: str = "第三人称"  # 叙事视角: 第一人称/第三人称/多视角
    tone: str = "中性"  # 基调: 温暖/冷峻/幽默/严肃
    pacing: str = "中等"  # 节奏: 快速/中等/缓慢
    
    writing_techniques: List[str] = field(default_factory=list)  # 写作手法
    language_features: Dict[str, str] = field(default_factory=dict)  # 语言特征
    structural_preferences: Dict[str, Any] = field(default_factory=dict)  # 结构偏好
    constraints: List[str] = field(default_factory=list)  # 创作约束
    
    def to_prompt_instruction(self) -> str:
        """将风格配置转换为AI可理解的提示指令"""
        parts = []
        
        if self.genre and self.genre != "通用":
            parts.append(f"【类型】{self.genre}" + (f"({self.sub_genre})" if self.sub_genre else ""))
        
        if self.author_style:
            style_map = {
                "海明威": "简洁有力，短句为主，少用形容词，冰山理论，对话驱动",
                "金庸": "武侠风格，半文半白，宏大叙事，人物刻画细腻，招式描写生动",
                "村上春树": "都市孤独感，隐喻丰富，超现实元素，细节描写精致",
                "鲁迅": "犀利批判，白话文典范，讽刺深刻，社会洞察力强",
                "古龙": "短句如诗，意境深远，悬疑氛围，哲理思辨",
                "J.K.罗琳": "魔法现实主义，成长主题，细节丰富，节奏明快",
                "东野圭吾": "推理严密，人性剖析，伏笔精妙，反转出人意料"
            }
            desc = style_map.get(self.author_style, f"模仿{self.author_style}的写作风格")
            parts.append(f"【作者风格】{desc}")
        
        if self.narrative_voice:
            voice_map = {
                "第一人称": "使用'我'的视角，主观性强，内心独白丰富",
                "第三人称": "全知或有限视角，客观叙述，适合复杂情节",
                "多视角": "轮流切换不同角色视角，立体呈现故事"
            }
            parts.append(f"【叙事视角】{voice_map.get(self.narrative_voice, self.narrative_voice)}")
        
        if self.tone and self.tone != "中性":
            tone_map = {
                "温暖": "温馨治愈，充满希望，情感真挚",
                "冷峻": "理性克制，氛围凝重，思考深刻",
                "幽默": "轻松诙谐，妙趣横生，令人会心一笑",
                "严肃": "庄重正式，探讨深刻议题，引人深思"
            }
            parts.append(f"【情感基调】{tone_map.get(self.tone, self.tone)}")
        
        if self.writing_techniques:
            tech_descriptions = {
                "倒叙": "采用倒叙手法，先揭示结果再追溯原因",
                "插叙": "在主线中插入回忆或背景故事",
                "多视角叙事": "从多个角色的角度讲述同一事件",
                "意识流": "展现角色内心思维流动，非线性叙事",
                "蒙太奇": "快速场景切换，平行剪辑式叙事",
                "伏笔埋设": "巧妙设置暗示和线索，为后续剧情铺垫",
                "悬念营造": "在关键节点制造紧张感和不确定性",
                "环境烘托": "通过环境描写映射人物心理和情绪",
                "对比映衬": "运用对比手法突出主题和人物性格",
                "象征隐喻": "使用象征物传达深层含义"
            }
            techniques = [tech_descriptions.get(t, t) for t in self.writing_techniques]
            parts.append(f"【写作手法】{'；'.join(techniques)}")
        
        if self.constraints:
            parts.append(f"【创作约束】{'；'.join(self.constraints)}")
        
        return "\n".join(parts)


@dataclass 
class StoryContext:
    """整个故事的完整上下文"""
    story_id: str = ""
    title: str = ""
    genre: str = ""
    style_profile: Optional[StyleProfile] = None
    
    chapters: List[ChapterContext] = field(default_factory=list)
    active_characters: Dict[str, Dict[str, str]] = field(default_factory=dict)  # 角色档案
    plot_lines: Dict[str, List[Dict]] = field(default_factory=dict)  # 多条情节线
    world_rules: List[str] = field(default_factory=list)  # 世界观规则
    established_facts: Set[str] = field(default_factory=set)  # 已确立的事实
    
    global_constraints: List[str] = field(default_factory=list)
    user_notes: List[str] = field(default_factory=list)
    version: int = 1
    last_updated: str = ""
    
    def __post_init__(self):
        if not self.last_updated:
            self.last_updated = datetime.now().isoformat()
        if self.style_profile is None:
            self.style_profile = StyleProfile()


class ContextMemory:
    """
    上下文记忆管理系统
    
    职责：
    1. 存储和管理所有章节的上下文信息
    2. 提供智能上下文检索和摘要功能
    3. 支持持久化到JSON文件
    4. 维护创作约束和风格的连续性
    """
    
    def __init__(self, storage_dir: str = "story_contexts"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        self.current_story: Optional[StoryContext] = None
        self._max_context_window: int = 5  # 保留最近5章的详细上下文
        
    def create_new_story(self, story_id: str, title: str = "", 
                        genre: str = "", style_config: Optional[Dict] = None) -> StoryContext:
        """创建新的故事上下文"""
        story = StoryContext(
            story_id=story_id,
            title=title,
            genre=genre
        )
        
        if style_config:
            story.style_profile = StyleProfile(**style_config)
            
        self.current_story = story
        return story
    
    def load_story(self, story_id: str) -> Optional[StoryContext]:
        """从文件加载故事上下文"""
        file_path = self.storage_dir / f"{story_id}_context.json"
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            story = StoryContext(
                story_id=data['story_id'],
                title=data.get('title', ''),
                genre=data.get('genre', ''),
                version=data.get('version', 1),
                last_updated=data.get('last_updated', '')
            )
            
            # 加载风格配置
            if 'style_profile' in data:
                sp = data['style_profile']
                story.style_profile = StyleProfile(
                    genre=sp.get('genre', '通用'),
                    sub_genre=sp.get('sub_genre', ''),
                    author_style=sp.get('author_style', ''),
                    narrative_voice=sp.get('narrative_voice', '第三人称'),
                    tone=sp.get('tone', '中性'),
                    pacing=sp.get('pacing', '中等'),
                    writing_techniques=sp.get('writing_techniques', []),
                    language_features=sp.get('language_features', {}),
                    structural_preferences=sp.get('structural_preferences', {}),
                    constraints=sp.get('constraints', [])
                )
            
            # 加载章节上下文
            for ch_data in data.get('chapters', []):
                ch = ChapterContext(
                    chapter_num=ch_data['chapter_num'],
                    title=ch_data.get('title', ''),
                    content_summary=ch_data.get('content_summary', ''),
                    word_count=ch_data.get('word_count', 0),
                    key_events=ch_data.get('key_events', []),
                    character_states=ch_data.get('character_states', {}),
                    plot_threads=ch_data.get('plot_threads', []),
                    emotional_tone=ch_data.get('emotional_tone', ''),
                    cliffhanger=ch_data.get('cliffhanger', ''),
                    writing_techniques_used=ch_data.get('writing_techniques_used', []),
                    metadata=ch_data.get('metadata', {}),
                    created_at=ch_data.get('created_at', '')
                )
                story.chapters.append(ch)
            
            # 加载其他数据
            story.active_characters = data.get('active_characters', {})
            story.plot_lines = data.get('plot_lines', {})
            story.world_rules = data.get('world_rules', [])
            story.established_facts = set(data.get('established_facts', []))
            story.global_constraints = data.get('global_constraints', [])
            story.user_notes = data.get('user_notes', [])
            
            self.current_story = story
            return story
            
        return None
    
    def save_story(self) -> bool:
        """保存当前故事上下文到文件"""
        if not self.current_story:
            return False
            
        self.current_story.last_updated = datetime.now().isoformat()
        self.current_story.version += 1
        
        data = asdict(self.current_story)
        
        # 处理set类型（established_facts）
        data['established_facts'] = list(self.current_story.established_facts)
        
        file_path = self.storage_dir / f"{self.current_story.story_id}_context.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        return True
    
    def add_chapter_context(self, chapter_num: int, content: str,
                           key_events: List[str] = None,
                           character_changes: Dict[str, str] = None,
                           plot_advancements: List[str] = None,
                           emotional_tone: str = "",
                           cliffhanger: str = "",
                           techniques_used: List[str] = None,
                           metadata: Dict = None) -> ChapterContext:
        """添加新章节的上下文信息"""
        if not self.current_story:
            raise ValueError("未初始化故事上下文")
            
        # 自动生成内容摘要（取前500字+最后200字）
        summary = self._generate_content_summary(content)
        
        ctx = ChapterContext(
            chapter_num=chapter_num,
            content_summary=summary,
            word_count=len(content),
            key_events=key_events or [],
            character_states=character_changes or {},
            plot_threads=plot_advancements or [],
            emotional_tone=emotional_tone,
            cliffhanger=cliffhanger,
            writing_techniques_used=techniques_used or [],
            metadata=metadata or {}
        )
        
        self.current_story.chapters.append(ctx)
        
        # 更新已确立事实
        if key_events:
            self.current_story.established_facts.update(key_events)
            
        # 更新角色状态
        if character_changes:
            for char, state in character_changes.items():
                if char not in self.current_story.active_characters:
                    self.current_story.active_characters[char] = {}
                self.current_story.active_characters[char].update({
                    'latest_state': state,
                    'last_appearance': f"第{chapter_num}章"
                })
        
        # 自动保存
        self.save_story()
        
        return ctx
    
    def get_context_for_next_chapter(self, next_chapter_num: int) -> Dict[str, Any]:
        """
        为生成下一章准备完整的上下文信息
        
        返回包含以下内容的字典：
        - previous_chapters_summary: 前序章节摘要
        - recent_context: 最近几章的详细信息
        - active_plot_threads: 当前活跃的情节线
        - character_situations: 各角色当前状况
        - style_consistency_instructions: 风格一致性指令
        - continuity_requirements: 连贯性要求
        - dynamic_adjustments: 动态调整建议
        """
        if not self.current_story or not self.current_story.chapters:
            return {'is_first_chapter': True}
            
        result = {}
        
        # 1. 前序章节总体摘要
        all_summaries = []
        for ch in self.current_story.chapters:
            if ch.content_summary:
                all_summaries.append(f"第{ch.chapter_num}章: {ch.content_summary[:200]}...")
        result['previous_chapters_summary'] = "\n".join(all_summaries[-3:])  # 最近3章
        
        # 2. 最近章节详细上下文
        recent_chapters = self.current_story.chapters[-self._max_context_window:]
        recent_context = []
        for ch in recent_chapters:
            context_entry = {
                'chapter': ch.chapter_num,
                'title': ch.title,
                'events': ch.key_events,
                'characters': ch.character_states,
                'plot_threads': ch.plot_threads,
                'cliffhanger': ch.cliffhanger,
                'emotional_tone': ch.emotional_tone
            }
            recent_context.append(context_entry)
        result['recent_context'] = recent_context
        
        # 3. 收集当前活跃的情节线
        all_plot_threads = set()
        for ch in self.current_story.chapters:
            all_plot_threads.update(ch.plot_threads)
        result['active_plot_threads'] = list(all_plot_threads)
        
        # 4. 角色当前状况
        result['character_situations'] = self.current_story.active_characters
        
        # 5. 风格一致性指令
        if self.current_story.style_profile:
            result['style_instructions'] = self.current_story.style_profile.to_prompt_instruction()
            # 统计已使用的写作手法
            used_techniques = set()
            for ch in self.current_story.chapters:
                used_techniques.update(ch.writing_techniques_used)
            result['used_writing_techniques'] = list(used_techniques)
        
        # 6. 连贯性要求
        continuity_reqs = []
        if self.current_story.chapters:
            last_ch = self.current_story.chapters[-1]
            if last_ch.cliffhanger:
                continuity_reqs.append(f"必须回应上一章悬念: {last_ch.cliffhanger}")
            if last_ch.emotional_tone:
                continuity_reqs.append(f"延续上一章的情感基调: {last_ch.emotional_tone}")
        
        if self.current_story.global_constraints:
            continuity_reqs.extend(self.current_story.global_constraints)
            
        result['continuity_requirements'] = continuity_reqs
        
        # 7. 动态调整建议
        result['dynamic_adjustments'] = self._generate_dynamic_adjustments(next_chapter_num)
        
        # 8. 已确立的事实（世界观、设定等）
        result['established_facts'] = list(self.current_story.established_facts)
        
        result['total_chapters'] = len(self.current_story.chapters)
        result['next_chapter_num'] = next_chapter_num
        
        return result
    
    def _generate_content_summary(self, content: str, max_length: int = 300) -> str:
        """生成内容摘要"""
        if len(content) <= max_length:
            return content
            
        # 取开头和结尾部分
        start = content[:max_length//2]
        end = content[-max_length//2:] if len(content) > max_length else ""
        
        return f"{start}...[中间省略]...{end}" if end else start
    
    def _generate_dynamic_adjustments(self, next_chapter_num: int) -> List[str]:
        """根据累积上下文动态生成调整建议"""
        adjustments = []
        
        if not self.current_story or len(self.current_story.chapters) < 2:
            return adjustments
            
        chapters = self.current_story.chapters
        
        # 分析节奏变化
        word_counts = [ch.word_count for ch in chapters[-3:]]
        if len(word_counts) >= 2:
            avg_words = sum(word_counts) / len(word_counts)
            if avg_words > 3000:
                adjustments.append("最近章节篇幅较长，建议适当控制本章长度，保持紧凑节奏")
            elif avg_words < 1500:
                adjustments.append("最近章节较短，可以适当展开细节描写")
        
        # 分析情感基调变化
        tones = [ch.emotional_tone for ch in chapters[-3:] if ch.emotional_tone]
        if len(set(tones)) > 1:
            adjustments.append("注意情感基调的自然过渡，避免突兀转变")
        
        # 情节线检查
        if len(chapters) >= 5:
            recent_threads = set()
            for ch in chapters[-3:]:
                recent_threads.update(ch.plot_threads)
            
            older_threads = set()
            for ch in chapters[:-3]:
                older_threads.update(ch.plot_threads)
                
            unresolved = older_threads - recent_threads
            if unresolved:
                adjustments.append(f"注意处理之前未完结的情节线: {', '.join(list(unresolved)[:3])}")
        
        # 角色平衡检查
        if self.current_story.active_characters:
            recent_chars = set()
            for ch in chapters[-2:]:
                recent_chars.update(ch.character_states.keys())
            
            inactive_chars = set(self.current_story.active_characters.keys()) - recent_chars
            if inactive_chars and len(chapters) > 3:
                adjustments.append(f"考虑让久未出现的角色回归: {', '.join(list(inactive_chars)[:2])}")
        
        # 章节数量提示
        if next_chapter_num % 5 == 0:
            adjustments.append(f"第{next_chapter_num}章是重要节点，适合安排转折点或小高潮")
        elif next_chapter_num % 10 == 0:
            adjustments.append(f"第{next_chapter_num}章是里程碑章节，建议回顾并推进主要冲突")
        
        return adjustments
    
    def update_global_constraints(self, constraints: List[str]):
        """更新全局创作约束"""
        if self.current_story:
            self.current_story.global_constraints.extend(constraints)
            self.save_story()
    
    def add_user_note(self, note: str):
        """添加用户备注"""
        if self.current_story:
            self.current_story.user_notes.append({
                'content': note,
                'timestamp': datetime.now().isoformat()
            })
            self.save_story()
    
    def add_world_rule(self, rule: str):
        """添加世界观规则"""
        if self.current_story:
            self.current_story.world_rules.append(rule)
            self.current_story.established_facts.add(rule)
            self.save_story()
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取故事统计信息"""
        if not self.current_story:
            return {}
            
        total_words = sum(ch.word_count for ch in self.current_story.chapters)
        all_techniques = set()
        for ch in self.current_story.chapters:
            all_techniques.update(ch.writing_techniques_used)
        
        return {
            'total_chapters': len(self.current_story.chapters),
            'total_words': total_words,
            'unique_characters': len(self.current_story.active_characters),
            'active_plot_threads': len(self._collect_all_plot_threads()),
            'techniques_used': list(all_techniques),
            'world_rules_count': len(self.current_story.world_rules),
            'version': self.current_story.version,
            'last_updated': self.current_story.last_updated
        }
    
    def _collect_all_plot_threads(self) -> Set[str]:
        """收集所有情节线"""
        threads = set()
        if self.current_story:
            for ch in self.current_story.chapters:
                threads.update(ch.plot_threads)
        return threads
    
    def export_context_for_prompt(self, next_chapter_num: int) -> str:
        """
        导出格式化的上下文信息，可直接注入到AI提示词中
        
        这是核心方法，将所有上下文转换为结构化的提示文本
        """
        context_data = self.get_context_for_next_chapter(next_chapter_num)
        
        if context_data.get('is_first_chapter'):
            return "[这是第一章，无前序章节上下文]"
        
        sections = []
        
        sections.append("=" * 60)
        sections.append("📚 前序章节概要")
        sections.append("=" * 60)
        sections.append(context_data.get('previous_chapters_summary', ''))
        
        # 最近章节详情
        recent = context_data.get('recent_context', [])
        if recent:
            sections.append("\n" + "=" * 60)
            sections.append("📖 最近章节详情")
            sections.append("=" * 60)
            for ch in recent[-2:]:  # 只显示最近2章
                sections.append(f"\n--- 第{ch['chapter']}章 ---")
                if ch.get('title'):
                    sections.append(f"标题: {ch['title']}")
                if ch.get('events'):
                    sections.append(f"关键事件: {'; '.join(ch['events'])}")
                if ch.get('characters'):
                    for char, state in ch['characters'].items():
                        sections.append(f"  • {char}: {state}")
                if ch.get('plot_threads'):
                    sections.append(f"情节推进: {'; '.join(ch['plot_threads'])}")
                if ch.get('cliffhanger'):
                    sections.append(f"⚠️ 悬念: {ch['cliffhanger']}")
        
        # 角色状况
        chars = context_data.get('character_situations', {})
        if chars:
            sections.append("\n" + "=" * 60)
            sections.append("👥 角色当前状况")
            sections.append("=" * 60)
            for char_name, info in chars.items():
                latest_state = info.get('latest_state', '未知')
                last_seen = info.get('last_appearance', '未知')
                sections.append(f"• {char_name}: {latest_state} (最后出现: {last_seen})")
        
        # 活跃情节线
        threads = context_data.get('active_plot_threads', [])
        if threads:
            sections.append("\n" + "=" * 60)
            sections.append("🔀 当前活跃情节线")
            sections.append("=" * 60)
            for i, thread in enumerate(threads[:8], 1):  # 最多显示8条
                sections.append(f"{i}. {thread}")
        
        # 风格一致性要求
        style_instr = context_data.get('style_instructions', '')
        if style_instr:
            sections.append("\n" + "=" * 60)
            sections.append("✍️ 创作风格要求（必须严格遵守）")
            sections.append("=" * 60)
            sections.append(style_instr)
            
            # 显示已使用的手法
            used = context_data.get('used_writing_techniques', [])
            if used:
                sections.append(f"\n已使用的写作手法: {', '.join(used)}")
        
        # 连贯性要求
        continuity = context_data.get('continuity_requirements', [])
        if continuity:
            sections.append("\n" + "=" * 60)
            sections.append("🔗 连贯性要求（必须满足）")
            sections.append("=" * 60)
            for req in continuity:
                sections.append(f"• {req}")
        
        # 动态调整建议
        adjustments = context_data.get('dynamic_adjustments', [])
        if adjustments:
            sections.append("\n" + "=" * 60)
            sections.append("💡 智能调整建议")
            sections.append("=" * 60)
            for adj in adjustments:
                sections.append(f"• {adj}")
        
        # 已确立的事实
        facts = context_data.get('established_facts', [])
        if facts:
            sections.append("\n" + "=" * 60)
            sections.append("📋 已确立的事实（不可矛盾）")
            sections.append("=" * 60)
            for fact in facts[:10]:  # 最多10条
                sections.append(f"✓ {fact}")
        
        sections.append("\n" + "=" * 60)
        sections.append(f"📊 上下文统计 | 已完成: {context_data.get('total_chapters', 0)}章 | 即将生成: 第{context_data.get('next_chapter_num', '?')}章")
        sections.append("=" * 60)
        
        return "\n".join(sections)
