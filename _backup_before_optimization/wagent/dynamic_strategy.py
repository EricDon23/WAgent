#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
动态策略调整系统 (Dynamic Strategy Adjustment System)

核心功能：
1. 基于累积上下文智能调整生成策略
2. 故事节奏控制与平衡
3. 创作性与一致性权衡管理
4. 多维度自适应优化
5. 实时策略反馈与调整建议

设计原则：
- 数据驱动：基于实际生成数据进行决策
- 渐进式调整：避免剧烈的策略突变
- 可解释性：所有调整都有明确的理由
- 用户可控：允许用户覆盖或微调策略
"""

import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from collections import deque


class StoryPhase(Enum):
    """故事阶段"""
    INTRODUCTION = "开篇期"  # 第1-3章
    DEVELOPMENT = "发展期"  # 第4-8章
    RISING_ACTION = "上升期"  # 第9-15章
    CLIMAX = "高潮期"  # 第16-20章
    RESOLUTION = "收尾期"  # 第21章以后


@dataclass
class GenerationStrategy:
    """生成策略配置"""
    temperature: float = 1.0  # 温度参数 (创造性)
    top_p: float = 0.9  # Top-P采样
    max_tokens: int = 4096  # 最大token数
    context_window: int = 5  # 引用的上下文章节数
    
    creativity_weight: float = 0.5  # 创造性权重
    consistency_weight: float = 0.5  # 一致性权重
    detail_level: float = 0.7  # 细节程度 (0-1)
    
    pacing_mode: str = "balanced"  # 节奏模式: fast/balanced/slow
    focus_areas: List[str] = field(default_factory=list)  # 重点关注的领域
    restrictions: List[str] = field(default_factory=list)  # 当前限制
    
    def to_dict(self) -> Dict:
        return {
            'temperature': self.temperature,
            'top_p': self.top_p,
            'max_tokens': self.max_tokens,
            'creativity_weight': self.creativity_weight,
            'consistency_weight': self.consistency_weight,
            'detail_level': self.detail_level,
            'pacing_mode': self.pacing_mode,
            'focus_areas': self.focus_areas,
            'restrictions': self.restrictions
        }


@dataclass
class StrategyAdjustment:
    """策略调整记录"""
    parameter: str  # 调整的参数名
    old_value: Any
    new_value: Any
    reason: str  # 调整原因
    chapter_num: int
    confidence: float = 0.8  # 调整置信度 (0-1)
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class DynamicStrategyManager:
    """
    动态策略管理器
    
    职责：
    1. 监控故事发展状态
    2. 分析创作质量和模式
    3. 自动调整生成策略
    4. 提供策略优化建议
    5. 维护策略历史记录
    """
    
    def __init__(self):
        self.current_strategy = GenerationStrategy()
        self.base_strategy = GenerationStrategy()
        
        self.adjustment_history: List[StrategyAdjustment] = []
        self.chapter_metrics: deque = deque(maxlen=20)  # 最近20章的指标
        
        # 阈值配置
        self._repetition_threshold = 0.7  # 重复度阈值
        self._pace_variance_threshold = 0.3  # 节奏变化阈值
        self._quality_threshold = 70  # 质量评分阈值
        
        # 统计数据
        self.total_adjustments = 0
        self.auto_adjustments = 0
        self.user_overrides = 0
        
    def analyze_and_adjust(self, 
                          chapter_num: int,
                          context_summary: Dict,
                          recent_quality_scores: List[float] = None,
                          user_feedback: Dict = None) -> Tuple[GenerationStrategy, List[str]]:
        """
        分析当前状态并调整策略
        
        Args:
            chapter_num: 当前章节号
            context_summary: 上下文摘要（来自ContextMemory）
            recent_quality_scores: 最近几章的质量评分
            user_feedback: 用户反馈
            
        Returns:
            (调整后的策略, 调整说明列表)
        """
        adjustments_made = []
        new_strategy = GenerationStrategy(**self.current_strategy.to_dict())
        
        # 1. 基于故事阶段的调整
        phase = self._determine_story_phase(chapter_num)
        phase_adjustments = self._adjust_for_phase(phase, chapter_num)
        if phase_adjustments:
            new_strategy, reasons = self._apply_adjustments(new_strategy, phase_adjustments, f"故事阶段: {phase.value}")
            adjustments_made.extend(reasons)
        
        # 2. 基于质量趋势的调整
        if recent_quality_scores and len(recent_quality_scores) >= 3:
            quality_adj = self._adjust_based_on_quality(recent_quality_scores, chapter_num)
            if quality_adj:
                new_strategy, reasons = self._apply_adjustments(new_strategy, quality_adj, "质量趋势分析")
                adjustments_made.extend(reasons)
        
        # 3. 基于上下文的节奏调整
        context_adj = self._adjust_based_on_context(context_summary, chapter_num)
        if context_adj:
            new_strategy, reasons = self._apply_adjustments(new_strategy, context_adj, "上下文分析")
            adjustments_made.extend(reasons)
        
        # 4. 基于用户反馈的调整
        if user_feedback:
            feedback_adj = self._adjust_based_on_feedback(user_feedback, chapter_num)
            if feedback_adj:
                new_strategy, reasons = self._apply_adjustments(new_strategy, feedback_adj, "用户反馈")
                adjustments_made.extend(reasons)
                self.user_overrides += 1
        
        # 5. 章节特殊节点调整
        node_adj = self._adjust_for_chapter_node(chapter_num)
        if node_adj:
            new_strategy, reasons = self._apply_adjustments(new_strategy, node_adj, f"章节节点(第{chapter_num}章)")
            adjustments_made.extend(reasons)
        
        # 记录调整
        if adjustments_made:
            self.current_strategy = new_strategy
            self.auto_adjustments += 1
            self.total_adjustments += len(adjustments_made)
        
        return new_strategy, adjustments_made
    
    def _determine_story_phase(self, chapter_num: int) -> StoryPhase:
        """确定当前故事阶段"""
        if chapter_num <= 3:
            return StoryPhase.INTRODUCTION
        elif chapter_num <= 8:
            return StoryPhase.DEVELOPMENT
        elif chapter_num <= 15:
            return StoryPhase.RISING_ACTION
        elif chapter_num <= 20:
            return StoryPhase.CLIMAX
        else:
            return StoryPhase.RESOLUTION
    
    def _adjust_for_phase(self, phase: StoryPhase, chapter_num: int) -> Dict[str, Any]:
        """根据故事阶段调整策略"""
        adjustments = {}
        
        phase_configs = {
            StoryPhase.INTRODUCTION: {
                'temperature': 1.15,  # 高创造性，建立世界观
                'creativity_weight': 0.6,
                'consistency_weight': 0.4,
                'detail_level': 0.8,  # 详细设定
                'focus_areas': ['世界观构建', '角色介绍', '氛围营造', '悬念设置'],
                'pacing_mode': 'balanced'
            },
            StoryPhase.DEVELOPMENT: {
                'temperature': 1.05,  # 平衡创意与连贯
                'creativity_weight': 0.5,
                'consistency_weight': 0.5,
                'detail_level': 0.7,
                'focus_areas': ['角色发展', '情节推进', '关系深化', '伏笔埋设'],
                'pacing_mode': 'balanced'
            },
            StoryPhase.RISING_ACTION: {
                'temperature': 1.0,   # 开始收紧
                'creativity_weight': 0.45,
                'consistency_weight': 0.55,
                'detail_level': 0.65,
                'focus_areas': ['冲突升级', '紧张感', '转折点', '线索收束'],
                'pacing_mode': 'fast'
            },
            StoryPhase.CLIMAX: {
                'temperature': 0.9,   # 高一致性，确保收束合理
                'creativity_weight': 0.35,
                'consistency_weight': 0.65,
                'detail_level': 0.8,  # 高潮需要细节
                'focus_areas': ['高潮场景', '情感爆发', '关键抉择', '真相揭示'],
                'pacing_mode': 'fast'
            },
            StoryPhase.RESOLUTION: {
                'temperature': 0.85,  # 低创造性，注重收束
                'creativity_weight': 0.3,
                'consistency_weight': 0.7,
                'detail_level': 0.6,
                'focus_areas': ['结局收束', '角色归宿', '主题升华', '余韵'],
                'pacing_mode': 'slow'
            }
        }
        
        return phase_configs.get(phase, {})
    
    def _adjust_based_on_quality(self, scores: List[float], chapter_num: int) -> Dict[str, Any]:
        """基于质量趋势调整"""
        adjustments = {}
        
        if len(scores) < 3:
            return adjustments
        
        # 计算趋势
        recent_avg = sum(scores[-3:]) / 3
        older_avg = sum(scores[-6:-3]) / 3 if len(scores) >= 6 else recent_avg
        
        trend = recent_avg - older_avg
        
        if trend < -10:  # 质量明显下降
            adjustments['temperature'] = max(0.7, self.current_strategy.temperature - 0.1)
            adjustments['consistency_weight'] = min(0.8, self.current_strategy.consistency_weight + 0.1)
            adjustments['restrictions'] = ['提高质量标准', '加强连贯性检查']
            
        elif trend > 10:  # 质量提升中
            adjustments['creativity_weight'] = min(0.7, self.current_strategy.creativity_weight + 0.05)
            
        if recent_avg < self._quality_threshold:
            adjustments['detail_level'] = min(0.9, self.current_strategy.detail_level + 0.1)
        
        return adjustments
    
    def _adjust_based_on_context(self, context: Dict, chapter_num: int) -> Dict[str, Any]:
        """基于上下文信息调整"""
        adjustments = {}
        
        total_chapters = context.get('total_chapters', 0)
        
        # 根据已完成的章节数调整
        if total_chapters > 10:
            # 后期章节，增加上下文权重
            adjustments['context_window'] = min(8, self.current_strategy.context_window + 1)
            adjustments['consistency_weight'] = min(0.75, self.current_strategy.consistency_weight + 0.05)
        
        # 检查是否有大量未解决的线索
        dynamic_adj = context.get('dynamic_adjustments', [])
        unresolved_count = sum(1 for adj in dynamic_adj if '未完结' in adj or '未处理' in adj)
        
        if unresolved_count > 2:
            adjustments['focus_areas'] = self.current_strategy.focus_areas + ['线索收束']
            adjustments['pacing_mode'] = 'balanced'  # 放慢节奏处理线索
        
        # 检查内容长度趋势
        # （这里简化处理，实际可从context中提取更多信息）
        
        return adjustments
    
    def _adjust_based_on_feedback(self, feedback: Dict, chapter_num: int) -> Dict[str, Any]:
        """根据用户反馈调整"""
        adjustments = {}
        
        satisfaction = feedback.get('satisfaction')  # 1-5分
        comments = feedback.get('comments', '')
        
        if satisfaction is not None:
            if satisfaction <= 2:  # 不满意
                adjustments['temperature'] = self.base_strategy.temperature  # 重置到基础值
                adjustments['creativity_weight'] = 0.5
                adjustments['restrictions'] = ['根据用户反馈重新调整方向']
                
            elif satisfaction >= 4:  # 满意
                adjustments['creativity_weight'] = min(0.7, self.current_strategy.creativity_weight + 0.05)
        
        # 关键词分析
        if comments:
            if any(word in comments for word in ['太长', '啰嗦', '冗长']):
                adjustments['detail_level'] = max(0.4, self.current_strategy.detail_level - 0.2)
                
            elif any(word in comments for word in ['太短', '不够', '展开']):
                adjustments['detail_level'] = min(0.95, self.current_strategy.detail_level + 0.15)
                adjustments['max_tokens'] = min(6000, self.current_strategy.max_tokens + 500)
                
            elif any(word in comments for word in ['无聊', '平淡', '没意思']):
                adjustments['temperature'] = min(1.3, self.current_strategy.temperature + 0.1)
                adjustments['pacing_mode'] = 'fast'
                
            elif any(word in comments for word in ['太快', '急', '赶']):
                adjustments['pacing_mode'] = 'slow'
                adjustments['detail_level'] = min(0.9, self.current_strategy.detail_level + 0.1)
        
        return adjustments
    
    def _adjust_for_chapter_node(self, chapter_num: int) -> Dict[str, Any]:
        """针对特殊章节节点的调整"""
        adjustments = {}
        
        # 每5章的小节点
        if chapter_num % 5 == 0 and chapter_num > 0:
            adjustments['temperature'] = min(1.2, self.current_strategy.temperature + 0.05)
            adjustments['focus_areas'] = self.current_strategy.focus_areas + ['小高潮/转折']
        
        # 每10章的大节点
        if chapter_num % 10 == 0 and chapter_num > 0:
            adjustments['detail_level'] = 0.85
            adjustments['max_tokens'] = min(5000, self.current_strategy.max_tokens + 300)
            adjustments['focus_areas'] = self.current_strategy.focus_areas + ['重要回顾/转折']
        
        # 第1章特殊处理
        if chapter_num == 1:
            adjustments['temperature'] = 1.15
            adjustments['creativity_weight'] = 0.6
            adjustments['detail_level'] = 0.8
        
        return adjustments
    
    def _apply_adjustments(self, 
                          strategy: GenerationStrategy, 
                          adjustments: Dict[str, Any],
                          reason: str) -> Tuple[GenerationStrategy, List[str]]:
        """应用调整并记录"""
        reasons = []
        
        for param, new_value in adjustments.items():
            if hasattr(strategy, param):
                old_value = getattr(strategy, param)
                if old_value != new_value:
                    setattr(strategy, param, new_value)
                    
                    # 记录调整
                    adjustment = StrategyAdjustment(
                        parameter=param,
                        old_value=old_value,
                        new_value=new_value,
                        reason=reason,
                        chapter_num=self.total_adjustments + 1  # 近似章节号
                    )
                    self.adjustment_history.append(adjustment)
                    
                    reasons.append(f"• {param}: {old_value} → {new_value} ({reason})")
        
        return strategy, reasons
    
    def get_current_strategy_report(self) -> Dict[str, Any]:
        """获取当前策略报告"""
        return {
            'current_config': self.current_strategy.to_dict(),
            'base_config': self.base_strategy.to_dict(),
            'total_adjustments': self.total_adjustments,
            'auto_adjustments': self.auto_adjustments,
            'user_overrides': self.user_overrides,
            'recent_adjustments': [
                {
                    'param': a.parameter,
                    'from': a.old_value,
                    'to': a.new_value,
                    'reason': a.reason,
                    'confidence': a.confidence
                }
                for a in self.adjustment_history[-5:]
            ]
        }
    
    def get_optimization_suggestions(self, context: Dict = None) -> List[str]:
        """提供优化建议"""
        suggestions = []
        
        strat = self.current_strategy
        
        # 检查温度设置
        if strat.temperature > 1.2:
            suggestions.append("💡 当前温度较高，如果发现内容发散，考虑降低至1.0以下")
        elif strat.temperature < 0.8:
            suggestions.append("💡 当前温度较低，如果内容过于保守，可适当提升以增加创意")
        
        # 检查一致性权重
        if strat.consistency_weight < 0.4:
            suggestions.append("⚠️ 一致性权重偏低，可能出现前后矛盾的风险")
        
        # 检查细节程度
        if strat.detail_level > 0.85:
            suggestions.append("📝 细节程度高，注意控制章节长度")
        
        # 基于上下文的建议
        if context:
            total_ch = context.get('total_chapters', 0)
            if total_ch > 15 and strat.context_window < 5:
                suggestions.append("📚 故事已进入后期，建议增加上下文窗口以确保全局一致性")
        
        return suggestions
    
    def reset_to_base(self):
        """重置到基础策略"""
        self.current_strategy = GenerationStrategy(**self.base_strategy.to_dict())
        self.adjustment_history.clear()
    
    def export_strategy_state(self) -> str:
        """导出策略状态为可读文本"""
        report = self.get_current_strategy_report()
        
        lines = [
            "=" * 60,
            "📊 动态策略报告",
            "=" * 60,
            "",
            "**当前策略配置**:",
            f"  • 温度 (创造性): {report['current_config']['temperature']}",
            f"  • 创造性权重: {report['current_config']['creativity_weight']}",
            f"  • 一致性权重: {report['current_config']['consistency_weight']}",
            f"  • 细节程度: {report['current_config']['detail_level']}",
            f"  • 节奏模式: {report['current_config']['pacing_mode']}",
            f"  • 关注领域: {', '.join(report['current_config']['focus_areas']) or '无'}",
            "",
            f"**统计**: 总调整{report['total_adjustments']}次 | 自动{report['auto_adjustments']}次 | 用户{report['user_overrides']}次",
            ""
        ]
        
        if report['recent_adjustments']:
            lines.append("**最近5次调整**:")
            for adj in report['recent_adjustments']:
                lines.append(f"  • {adj['param']}: {adj['from']} → {adj['to']} ({adj['reason']})")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)
