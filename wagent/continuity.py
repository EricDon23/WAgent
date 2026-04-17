#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
章节连贯性管理器 (Chapter Continuity Manager)

核心功能：
1. 实时监控章节间的叙事连贯性
2. 自动检测潜在矛盾和不一致
3. 角色行为与性格一致性验证
4. 情节线追踪与逻辑检查
5. 世界观规则一致性保障
6. 连贯性评分与质量报告

设计原则：
- 主动性：在生成前预防问题，生成后检测问题
- 全面性：覆盖角色/情节/时间/空间/风格多个维度
- 可解释性：提供具体的问题定位和修复建议
- 渐进式：随着故事发展逐步建立约束网络
"""

import re
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ContinuityIssueType(Enum):
    """连贯性问题类型"""
    CHARACTER_CONTRADICTION = "角色矛盾"
    PLOT_HOLE = "剧情漏洞"
    TIMELINE_ERROR = "时间线错误"
    WORLD_RULE_VIOLATION = "世界观违规"
    STYLE_INCONSISTENCY = "风格不一致"
    LOGICAL_CONTRADICTION = "逻辑矛盾"
    UNRESOLVED_THREAD = "未完结线索"
    REPETITIVE_CONTENT = "内容重复"


@dataclass
class ContinuityIssue:
    """连贯性问题记录"""
    issue_type: ContinuityIssueType
    severity: str  # critical/major/minor/suggestion
    location: str  # 问题位置描述
    description: str  # 问题描述
    suggestion: str  # 修复建议
    chapter_range: Tuple[int, int] = (0, 0)  # 涉及的章节范围
    detected_at: str = ""
    
    def __post_init__(self):
        if not self.detected_at:
            self.detected_at = datetime.now().isoformat()


@dataclass
class ContinuityScore:
    """连贯性评分"""
    overall_score: float  # 0-100
    character_consistency: float  # 角色一致性
    plot_coherence: float  # 情节连贯性
    world_consistency: float  # 世界观一致性
    style_consistency: float  # 风格一致性
    timeline_accuracy: float  # 时间线准确性
    
    details: List[str] = field(default_factory=list)
    
    @property
    def grade(self) -> str:
        if self.overall_score >= 90:
            return "A (优秀)"
        elif self.overall_score >= 80:
            return "B (良好)"
        elif self.overall_score >= 70:
            return "C (合格)"
        elif self.overall_score >= 60:
            return "D (需改进)"
        else:
            return "F (不合格)"


class ContinuityManager:
    """
    章节连贯性管理器
    
    职责：
    1. 维护故事的连贯性约束网络
    2. 在新章节生成前进行预检
    3. 在新章节完成后进行后验
    4. 提供实时连贯性反馈
    5. 积累和更新故事状态模型
    """
    
    def __init__(self):
        self.issues: List[ContinuityIssue] = []
        self.character_profiles: Dict[str, Dict[str, Any]] = {}  # 角色详细档案
        self.timeline: List[Dict[str, Any]] = []  # 时间线事件
        self.active_plot_threads: Dict[str, Dict] = {}  # 活跃的情节线
        self.established_facts: Set[str] = set()  # 已确立的事实
        self.style_markers: List[str] = []  # 风格标记
        self.chapter_summaries: List[Tuple[int, str]] = []  # 章节摘要历史
        
        # 统计数据
        self.total_checks = 0
        self.total_issues_found = 0
        
    def pre_chapter_check(self, chapter_num: int, 
                         proposed_outline: str,
                         context_data: Dict) -> Tuple[bool, List[ContinuityIssue]]:
        """
        新章节生成前的预检
        
        检查项：
        - 与前序内容的潜在冲突
        - 角色行为的合理性
        - 时间线的连续性
        - 情节推进的逻辑性
        """
        issues = []
        
        # 1. 角色一致性预检
        char_issues = self._check_character_consistency_pre(chapter_num, proposed_outline, context_data)
        issues.extend(char_issues)
        
        # 2. 时间线连续性预检
        time_issues = self._check_timeline_continuity(chapter_num, context_data)
        issues.extend(time_issues)
        
        # 3. 情节逻辑预检
        plot_issues = self._check_plot_logic(chapter_num, proposed_outline, context_data)
        issues.extend(plot_issues)
        
        # 4. 世界观合规性预检
        world_issues = self._check_world_rules(proposed_outline, context_data)
        issues.extend(world_issues)
        
        self.total_checks += 1
        self.total_issues_found += len(issues)
        self.issues.extend(issues)
        
        # 判断是否可以继续（critical级别的问题会阻止生成）
        critical_issues = [i for i in issues if i.severity == 'critical']
        can_proceed = len(critical_issues) == 0
        
        return can_proceed, issues
    
    def post_chapter_validation(self, chapter_num: int,
                               content: str,
                               actual_events: List[str],
                               context_data: Dict) -> Tuple[ContinuityScore, List[ContinuityIssue]]:
        """
        新章节完成后的后验分析
        
        更新内部状态并检测实际产生的问题
        """
        issues = []
        
        # 1. 内容重复检测
        repetition_issues = self._check_content_repetition(chapter_num, content)
        issues.extend(repetition_issues)
        
        # 2. 风格一致性验证
        style_issues = self._validate_style_consistency(content, context_data)
        issues.extend(style_issues)
        
        # 3. 更新内部状态模型
        self._update_state_models(chapter_num, content, actual_events, context_data)
        
        # 4. 计算连贯性评分
        score = self._calculate_consistency_score(issues, context_data)
        
        self.issues.extend(issues)
        
        return score, issues
    
    def _check_character_consistency_pre(self, chapter_num: int, 
                                        outline: str,
                                        context: Dict) -> List[ContinuityIssue]:
        """检查角色行为是否与已建立的档案一致"""
        issues = []
        characters = context.get('character_situations', {})
        
        for char_name, char_info in characters.items():
            profile = self.character_profiles.get(char_name, {})
            
            if profile:
                # 检查是否有已知的行为模式或性格特征
                established_traits = profile.get('traits', [])
                last_state = char_info.get('latest_state', '')
                
                # 如果角色突然出现完全相反的行为，标记为潜在问题
                if last_state and profile.get('last_known_state'):
                    if self._is_contradiction(profile['last_known_state'], last_state):
                        issue = ContinuityIssue(
                            issue_type=ContinuityIssueType.CHARACTER_CONTRADICTION,
                            severity="major",
                            location=f"第{chapter_num}章 - {char_name}",
                            description=f"角色'{char_name}'的状态变化可能过于突兀: 从'{profile['last_known_state']}'变为'{last_state}'",
                            suggestion=f"建议在第{chapter_num}章增加过渡场景或心理描写来解释这一变化",
                            chapter_range=(profile.get('last_appearance', 1), chapter_num)
                        )
                        issues.append(issue)
        
        return issues
    
    def _check_timeline_continuity(self, chapter_num: int,
                                  context: Dict) -> List[ContinuityIssue]:
        """检查时间线的连续性"""
        issues = []
        
        recent_context = context.get('recent_context', [])
        if len(recent_context) >= 2:
            # 检查相邻章节的时间逻辑
            prev_chapter = recent_context[-1]
            prev_cliffhanger = prev_chapter.get('cliffhanger', '')
            
            if prev_cliffhanger:
                # 确保新一章回应了上一章的悬念
                pass  # 这个会在plot_logic中更详细检查
        
        return issues
    
    def _check_plot_logic(self, chapter_num: int,
                         outline: str,
                         context: Dict) -> List[ContinuityIssue]:
        """检查情节推进的逻辑性"""
        issues = []
        
        active_threads = context.get('active_plot_threads', [])
        
        # 检查是否有长期未处理的情节线
        if len(self.chapter_summaries) > 5:
            old_threads = set()
            for ch_num, summary in self.chapter_summaries[:-3]:
                # 简化的情节提取（实际应用中可用NLP）
                old_threads.update(self._extract_plot_mentions(summary))
            
            current_thread_set = set(active_threads)
            unresolved = old_threads - current_thread_set
            
            if len(unresolved) > 3 and chapter_num > 5:
                issue = ContinuityIssue(
                    issue_type=ContinuityIssueType.UNRESOLVED_THREAD,
                    severity="minor",
                    location=f"第{chapter_num}章",
                    description=f"发现{len(unresolved)}个可能被遗忘的情节线",
                    suggestion=f"考虑在本章或近期章节中提及或收束以下线索: {', '.join(list(unresolved)[:3])}",
                    chapter_range=(1, chapter_num)
                )
                issues.append(issue)
        
        return issues
    
    def _check_world_rules(self, outline: str,
                          context: Dict) -> List[ContinuityIssue]:
        """检查是否符合已确立的世界观规则"""
        issues = []
        world_rules = context.get('established_facts', [])
        
        # 这里可以实现具体的规则检查逻辑
        # 例如：如果设定了"魔法系统"，检查是否违反了魔法限制等
        
        return issues
    
    def _check_content_repetition(self, chapter_num: int,
                                 content: str) -> List[ContinuityIssue]:
        """检测与前序章节的内容重复"""
        issues = []
        
        if len(self.chapter_summaries) < 2:
            return issues
        
        # 简单的重复检测（基于关键词重叠）
        current_keywords = set(self._extract_key_phrases(content))
        
        for prev_ch_num, prev_summary in self.chapter_summaries[-3:]:
            prev_keywords = set(self._extract_key_phrases(prev_summary))
            
            overlap = current_keywords & prev_keywords
            overlap_ratio = len(overlap) / max(len(current_keywords), 1)
            
            if overlap_ratio > 0.7:  # 70%以上关键词重复
                issue = ContinuityIssue(
                    issue_type=ContinuityIssueType.REPETITIVE_CONTENT,
                    severity="suggestion",
                    location=f"第{chapter_num}章 vs 第{prev_ch_num}章",
                    description=f"本章与第{prev_ch_num}章内容相似度较高 ({overlap_ratio:.0%})",
                    suggestion="考虑增加新的情节元素或改变叙述角度以避免重复感",
                    chapter_range=(prev_ch_num, chapter_num)
                )
                issues.append(issue)
        
        return issues
    
    def _validate_style_consistency(self, content: str,
                                   context: Dict) -> List[ContinuityIssue]:
        """验证写作风格的一致性"""
        issues = []
        
        style_config = context.get('style_instructions', '')
        if not style_config or len(self.chapter_summaries) < 2:
            return issues
        
        # 提取当前章节的风格标记
        current_markers = self._detect_style_markers(content)
        
        # 与历史风格对比
        if self.style_markers:
            marker_overlap = set(current_markers) & set(self.style_markers[-5:])
            
            # 如果风格突变
            if len(current_markers) > 0 and len(marker_overlap) / len(current_markers) < 0.3:
                issue = ContinuityIssue(
                    issue_type=ContinuityIssueType.STYLE_INCONSISTENCY,
                    severity="minor",
                    location=f"第{chapter_num}章",
                    description="检测到写作风格可能与前序章节存在差异",
                    suggestion="回顾之前章节的叙事风格，保持语言风格的一致性",
                    chapter_range=(max(1, chapter_num-3), chapter_num)
                )
                issues.append(issue)
        
        self.style_markers.extend(current_markers)
        
        return issues
    
    def _update_state_models(self, chapter_num: int,
                            content: str,
                            events: List[str],
                            context: Dict):
        """更新内部状态模型"""
        # 更新章节摘要
        summary = content[:500] if content else ""
        self.chapter_summaries.append((chapter_num, summary))
        
        # 更新角色档案
        characters = context.get('character_situations', {})
        for char_name, char_info in characters.items():
            if char_name not in self.character_profiles:
                self.character_profiles[char_name] = {
                    'first_appearance': chapter_num,
                    'traits': [],
                    'state_history': []
                }
            
            profile = self.character_profiles[char_name]
            latest_state = char_info.get('latest_state', '')
            if latest_state:
                profile['last_known_state'] = latest_state
                profile['last_appearance'] = chapter_num
                profile['state_history'].append({
                    'chapter': chapter_num,
                    'state': latest_state
                })
        
        # 更新事实库
        facts = context.get('established_facts', [])
        self.established_facts.update(facts)
        
        # 更新活跃情节线
        threads = context.get('active_plot_threads', [])
        for thread in threads:
            if thread not in self.active_plot_threads:
                self.active_plot_threads[thread] = {
                    'introduced': chapter_num,
                    'mentions': [chapter_num]
                }
            else:
                self.active_plot_threads[thread]['mentions'].append(chapter_num)
    
    def _calculate_consistency_score(self, issues: List[ContinuityIssue],
                                    context: Dict) -> ContinuityScore:
        """计算综合连贯性评分"""
        # 基础分100分，根据问题扣分
        score = 100.0
        
        critical_count = sum(1 for i in issues if i.severity == 'critical')
        major_count = sum(1 for i in issues if i.severity == 'major')
        minor_count = sum(1 for i in issues if i.severity == 'minor')
        suggestion_count = sum(1 for i in issues if i.severity == 'suggestion')
        
        # 扣分规则
        score -= critical_count * 25
        score -= major_count * 15
        score -= minor_count * 8
        score -= suggestion_count * 2
        
        score = max(0, min(100, score))
        
        # 各维度评分（简化版）
        char_issues = [i for i in issues if i.issue_type == ContinuityIssueType.CHARACTER_CONTRADICTION]
        char_score = max(0, 100 - len(char_issues) * 20)
        
        plot_issues = [i for i in issues if i.issue_type in [
            ContinuityIssueType.PLOT_HOLE, ContinuityIssueType.UNRESOLVED_THREAD
        ]]
        plot_score = max(0, 100 - len(plot_issues) * 15)
        
        world_issues = [i for i in issues if i.issue_type == ContinuityIssueType.WORLD_RULE_VIOLATION]
        world_score = max(0, 100 - len(world_issues) * 25)
        
        style_issues = [i for i in issues if i.issue_type == ContinuityIssueType.STYLE_INCONSISTENCY]
        style_score = max(0, 100 - len(style_issues) * 10)
        
        time_issues = [i for i in issues if i.issue_type == ContinuityIssueType.TIMELINE_ERROR]
        time_score = max(0, 100 - len(time_issues) * 20)
        
        details = []
        if critical_count > 0:
            details.append(f"⚠️ 发现{critical_count}个严重问题需立即处理")
        if major_count > 0:
            details.append(f"• {major_count}个重要问题")
        if minor_count > 0:
            details.append(f"• {minor_count}个小问题")
        if suggestion_count > 0:
            details.append(f"💡 {suggestion_count}个优化建议")
        
        return ContinuityScore(
            overall_score=score,
            character_consistency=char_score,
            plot_coherence=plot_score,
            world_consistency=world_score,
            style_consistency=style_score,
            timeline_accuracy=time_score,
            details=details
        )
    
    def _is_contradiction(self, state1: str, state2: str) -> bool:
        """判断两个状态是否构成矛盾"""
        contradictions = [
            ('生', '死'),
            ('在', '不在'),
            ('知道', '不知道'),
            ('喜欢', '讨厌'),
            ('信任', '不信任'),
            (' ally ', ' enemy ')
        ]
        
        s1, s2 = state1.lower(), state2.lower()
        for word1, word2 in contradictions:
            if (word1 in s1 and word2 in s2) or (word2 in s1 and word1 in s2):
                return True
        
        return False
    
    def _extract_plot_mentions(self, text: str) -> List[str]:
        """从文本中提取情节相关词汇（简化版）"""
        # 实际应用中可以使用NLP工具进行实体抽取
        words = re.findall(r'[\u4e00-\u9fa5]{2,}', text)
        return words[:20]  # 返回前20个中文词
    
    def _extract_key_phrases(self, content: str) -> List[str]:
        """提取关键短语"""
        # 简化实现：提取常见的故事元素模式
        patterns = [
            r'[\u4e00-\u9fa5]+说',
            r'[\u4e00-\u9fa5]+想到',
            r'[\u4e00-\u9fa5]+发现',
            r'[\u4e00-\u9fa5]+决定',
            r'突然',
            r'原来',
            r'竟然',
        ]
        
        phrases = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            phrases.extend(matches[:5])
        
        return phrases
    
    def _detect_style_markers(self, content: str) -> List[str]:
        """检测文本中的风格标记"""
        markers = []
        
        # 句式长度分布
        sentences = re.split(r'[。！？]', content)
        avg_len = sum(len(s) for s in sentences) / max(len(sentences), 1)
        
        if avg_len < 20:
            markers.append("短句为主")
        elif avg_len > 50:
            markers.append("长句为主")
        
        # 特定表达方式
        if content.count('"') + content.count('"') > 10:
            markers.append("对话密集")
        
        if re.search(r'[?!]{2,}', content):
            markers.append("情绪强烈")
        
        if len(re.findall(r'[a-zA-Z]', content)) > 5:
            markers.append("包含外文")
        
        return markers
    
    def get_continuity_report(self) -> Dict[str, Any]:
        """生成完整的连贯性报告"""
        # 按严重程度分类问题
        by_severity = {'critical': [], 'major': [], 'minor': [], 'suggestion': []}
        for issue in self.issues:
            by_severity[issue.severity].append(issue)
        
        # 按类型分类
        by_type = {}
        for issue in self.issues:
            t = issue.issue_type.value
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(issue)
        
        return {
            'total_issues': len(self.issues),
            'by_severity': {k: len(v) for k, v in by_severity.items()},
            'by_type': {k: len(v) for k, v in by_type.items()},
            'total_checks': self.total_checks,
            'characters_tracked': len(self.character_profiles),
            'active_plot_threads': len(self.active_plot_threads),
            'established_facts_count': len(self.established_facts),
            'chapters_processed': len(self.chapter_summaries),
            'recent_critical_issues': by_severity['critical'][-5:] if by_severity['critical'] else [],
            'recent_major_issues': by_severity['major'][-5:] if by_severity['major'] else []
        }
    
    def get_context_for_generation(self) -> str:
        """获取用于生成的连贯性上下文指令"""
        if not self.issues and not self.character_profiles:
            return ""
        
        instructions = []
        
        # 关键提醒
        recent_major = [i for i in self.issues[-10:] if i.severity in ['critical', 'major']]
        if recent_major:
            instructions.append("⚠️ 连贯性注意事项:")
            for issue in recent_major[-3:]:
                instructions.append(f"  • {issue.description}")
                instructions.append(f"    → 建议: {issue.suggestion}")
        
        # 角色状态提醒
        if self.character_profiles:
            instructions.append("\n📋 角色状态参考:")
            for char_name, profile in list(self.character_profiles.items())[-5:]:
                if profile.get('last_known_state'):
                    instructions.append(f"  • {char_name}: {profile['last_known_state']}")
        
        # 未完结线索提醒
        unresolved = [t for t, info in self.active_plot_threads.items() 
                     if len(info.get('mentions', [])) <= 2]
        if unresolved:
            instructions.append(f"\n🔀 待发展的情节线 ({len(unresolved)}条):")
            for thread in unresolved[:5]:
                instructions.append(f"  • {thread}")
        
        return "\n".join(instructions)
