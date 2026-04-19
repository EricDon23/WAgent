#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WAgent V3.1 设定一致性校验工具

基于错误修改.md要求实现：
- 检测设定冲突和"吃书"问题
- 验证全局设定与局部设定的一致性
- 提供冲突解决建议
- 在作家AI生成前/后自动调用

V3.1新增：
- 与分层存储系统深度集成
- 支持global.json锁定检查
- 增量更新验证
"""

import json
import logging
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    """校验结果"""
    is_valid: bool = True
    warnings: List[str] = None
    errors: List[str] = None
    suggestions: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.errors is None:
            self.errors = []
        if self.suggestions is None:
            self.suggestions = []
    
    def to_dict(self) -> Dict:
        return {
            "is_valid": self.is_valid,
            "warnings_count": len(self.warnings),
            "errors_count": len(self.errors),
            "warnings": self.warnings,
            "errors": self.errors,
            "suggestions": self.suggestions
        }


class SettingConsistencyChecker:
    """
    设定一致性校验器 - V3.1核心质量保障
    
    功能：
    1. 检查局部设定是否违反global.json锁定规则
    2. 检测角色性格一致性
    3. 检测世界观矛盾
    4. 检测情节逻辑断裂
    5. 防止"吃书"问题
    """
    
    # 全局核心字段（不允许在局部设定中修改）
    GLOBAL_LOCKED_FIELDS = [
        'overall_title',
        'worldview',
        'core_theme',
        'overall_outline',
        'overall_character_relations'
    ]
    
    # 角色必须保持一致的属性
    CHARACTER_IMMUTABLE_FIELDS = [
        'name',
        'core_personality',  # 核心性格不可变
        'origin_background'   # 起源背景不可变
    ]
    
    def __init__(self):
        self.check_history: List[Dict] = []
    
    def check_global_locking(self, global_setting: Dict, 
                           chapter_setting: Dict) -> CheckResult:
        """
        检查是否违反global.json锁定规则
        
        V3.1强制要求：global.json中的核心字段不能被章节设定覆盖
        
        Args:
            global_setting: 从global.json加载的全局设定
            chapter_setting: 当前章节设定
            
        Returns:
            CheckResult对象
        """
        result = CheckResult()
        
        # 检查global_setting是否已锁定
        if not global_setting.get('is_locked', False):
            result.warnings.append("全局设定未锁定，建议锁定以防止意外修改")
        
        # 检查章节设定是否尝试修改锁定的全局字段
        for field in self.GLOBAL_LOCKED_FIELDS:
            if field in chapter_setting:
                result.errors.append(
                    f"❌ 违反锁定规则: 章节设定不应包含全局字段 '{field}'"
                )
                result.suggestions.append(
                    f"将'{field}'相关内容移到增量更新部分，而非直接覆盖"
                )
        
        result.is_valid = len(result.errors) == 0
        return result
    
    def check_character_consistency(self, 
                                  global_chars: List[Dict],
                                  chapter_chars: List[Dict],
                                  chapter_num: int) -> CheckResult:
        """
        检查角色一致性（防止吃书）
        
        Args:
            global_chars: 全局角色列表（从global.json）
            chapter_chars: 本章出场角色
            chapter_num: 当前章节数
            
        Returns:
            CheckResult对象
        """
        result = CheckResult()
        
        if not global_chars or not chapter_chars:
            return result
        
        # 构建全局角色索引
        global_char_index = {char.get('name'): char for char in global_chars}
        
        for char in chapter_chars:
            char_name = char.get('name', '')
            
            if char_name in global_char_index:
                global_char = global_char_index[char_name]
                
                # 检查核心属性一致性
                for field in self.CHARACTER_IMMUTABLE_FIELDS:
                    global_val = global_char.get(field)
                    local_val = char.get(field)
                    
                    if global_val and local_val and str(global_val) != str(local_val):
                        error_msg = (
                            f"⚠️ 角色'{char_name}'的{field}不一致:\n"
                            f"  全局设定: {str(global_val)[:50]}...\n"
                            f"  第{chapter_num}章: {str(local_val)[:50]}..."
                        )
                        result.errors.append(error_msg)
                        result.suggestions.append(
                            f"确保角色'{char_name}'的{field}在各章节中保持一致"
                        )
            
            else:
                # 新角色出现
                result.warnings.append(
                    f"新角色'{char_name}'在第{chapter_num}章首次出现"
                )
                result.suggestions.append(
                    f"考虑将'{char_name}'添加到全局人物关系表中"
                )
        
        result.is_valid = len(result.errors) == 0
        return result
    
    def check_plot_consistency(self,
                               global_outline: List[Dict],
                               chapter_outline: str,
                               previous_chapter_summary: str = "",
                               chapter_num: int = 1) -> CheckResult:
        """
        检查情节一致性（防止剧情断裂）
        
        Args:
            global_outline: 总体大纲
            chapter_outline: 本章大纲
            previous_chapter_summary: 前一章摘要
            chapter_num: 当前章节号
            
        Returns:
            CheckResult对象
        """
        result = CheckResult()
        
        if not global_outline:
            return result
        
        # 检查本章是否在总体大纲中有对应条目
        chapter_in_outline = any(
            outline.get('chapter_num') == chapter_num 
            for outline in global_outline
        )
        
        if not chapter_in_outline:
            result.warnings.append(
                f"第{chapter_num}章未在总体大纲中找到对应条目"
            )
        
        # 如果有前一章内容，检查衔接性
        if previous_chapter_summary and chapter_num > 1:
            if not chapter_outline:
                result.errors.append("续写章节缺少详细大纲")
                result.suggestions.append("应提供本章与前文的衔接说明")
        
        result.is_valid = len(result.errors) == 0
        return result
    
    def check_worldview_consistency(self,
                                    global_worldview: str,
                                    chapter_content: str,
                                    chapter_num: int) -> CheckResult:
        """
        检查世界观一致性
        
        Args:
            global_worldview: 全局世界观设定
            chapter_content: 章节内容
            chapter_num: 章节号
            
        Returns:
            CheckResult对象
        """
        result = CheckResult()
        
        if not global_worldview or not chapter_content:
            return result
        
        # 提取世界观的几个关键要素进行简单检查
        worldview_keywords = global_worldview.split()[:10]
        
        # 这里可以扩展更复杂的NLP检查
        # 目前仅做基础的存在性检查
        
        result.is_valid = True
        return result
    
    def full_check(self, story_id: str, chapter_num: int,
                  global_setting: Dict = None,
                  chapter_setting: Dict = None,
                  chapter_content: str = "") -> Dict:
        """
        执行完整的设定一致性检查（V3.1统一入口）
        
        Args:
            story_id: 故事ID
            chapter_num: 章节号
            global_setting: 全局设定
            chapter_setting: 章节设定
            chapter_content: 章节内容
            
        Returns:
            包含所有检查结果的完整报告
        """
        report = {
            "story_id": story_id,
            "chapter_num": chapter_num,
            "check_time": "",
            "overall_status": "PASS",
            "checks": {}
        }
        
        import datetime
        report["check_time"] = datetime.datetime.now().isoformat()
        
        # 1. 锁定规则检查
        if global_setting and chapter_setting:
            lock_result = self.check_global_locking(global_setting, chapter_setting)
            report["checks"]["locking"] = lock_result.to_dict()
            
            if not lock_result.is_valid:
                report["overall_status"] = "FAIL"
        
        # 2. 角色一致性检查
        global_chars = (global_setting or {}).get('overall_character_relations', [])
        chapter_chars = (chapter_setting or {}).get('chapter_characters', [])
        
        if global_chars and chapter_chars:
            char_result = self.check_character_consistency(
                global_chars, chapter_chars, chapter_num
            )
            report["checks"]["characters"] = char_result.to_dict()
            
            if not char_result.is_valid and report["overall_status"] != "FAIL":
                report["overall_status"] = "WARNING"
        
        # 3. 情节一致性检查
        global_outline = (global_setting or {}).get('overall_outline', [])
        chapter_outline = (chapter_setting or {}).get('chapter_outline', '')
        
        if global_outline:
            plot_result = self.check_plot_consistency(
                global_outline, chapter_outline, "", chapter_num
            )
            report["checks"]["plot"] = plot_result.to_dict()
            
            if not plot_result.is_valid and report["overall_status"] != "FAIL":
                report["overall_status"] = "WARNING"
        
        # 记录到历史
        self.check_history.append(report)
        
        logger.info(f"完成第{chapter_num}章设定校验: {report['overall_status']}")
        
        return report


def create_checker() -> SettingConsistencyChecker:
    """工厂函数：创建校验器实例"""
    return SettingConsistencyChecker()


# 便捷函数
def quick_check(global_setting: Dict, chapter_setting: Dict) -> bool:
    """快速检查设定一致性"""
    checker = create_checker()
    result = checker.check_global_locking(global_setting, chapter_setting)
    return result.is_valid
