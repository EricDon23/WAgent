#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
交互式判断工具模块

功能：
1. Y/N 交互式确认（大小写不敏感）- 核心功能
2. 多选项交互选择
3. 自定义提示输入
4. 输入验证与重试机制
5. 历史记录与上下文感知

核心特性：
- ✅ 大小写不敏感：Y/y/YES/yes/是 → True
- ✅ 多种表达支持：是/否/OK/取消/继续/停止等
- ✅ 自动重试机制：可配置最大重试次数
- ✅ 默认值支持：超时或无效输入时返回默认值
- ✅ 输入历史记录：便于调试和上下文感知

使用示例:
    from wagent.utils.interactive import InteractivePrompt, confirm
    
    # 方式1: 使用类实例
    prompt = InteractivePrompt()
    if prompt.confirm("是否继续？"):
        print("用户选择了是")
    
    # 方式2: 使用便捷函数
    if confirm("确认删除？", default=False):
        delete_file()
"""

import sys
import re
from typing import List, Optional, Callable, Any, Union, Dict
from datetime import datetime


class InteractivePrompt:
    """
    交互式提示工具类
    
    提供统一的用户交互接口，核心功能：
    - Y/N 确认（大小写不敏感）
    - 多选项选择
    - 文本输入
    - 数字输入
    - 输入验证与重试
    
    设计原则：
    - 容错性强（支持各种输入格式）
    - 用户友好（清晰的提示信息）
    - 可配置性高（可自定义行为）
    - 国际化友好（支持中英文混合）
    
    Attributes:
        case_insensitive: 是否大小写不敏感
        max_retries: 最大重试次数
        default_value: 超过重试次数后的默认返回值
    """
    
    def __init__(self, case_insensitive: bool = True, 
                 max_retries: int = 3,
                 default_value: Any = None):
        """
        初始化交互式提示工具
        
        Args:
            case_insensitive: 是否大小写不敏感（默认True）
            max_retries: 最大重试次数（默认3）
            default_value: 超过重试次数后的默认返回值
        """
        self.case_insensitive = case_insensitive
        self.max_retries = max_retries
        self.default_value = default_value
        
        # 输入历史（用于上下文感知和调试）
        self.history: List[Dict[str, Any]] = []
        
        # 预编译正则表达式（提升性能）
        self._yes_pattern = re.compile(
            r'^(y|yes|yep|yeah|ok|okay|是|是的?|好|好的?|确定|继续|confirm|true|t|1)$',
            re.IGNORECASE if case_insensitive else 0
        )
        
        self._no_pattern = re.compile(
            r'^(n|no|nope|not|否|取消|不|停止|结束|退出|放弃|cancel|false|f|0)$',
            re.IGNORECASE if case_insensitive else 0
        )
        
        # 标准化映射表（用于快速查找）
        self._yes_variants = {
            'y', 'yes', 'yep', 'yeah', 'ok', 'okay',
            '是', '是的', '好', '好的', '确定', '继续',
            '1', 'true', 't'
        }
        
        self._no_variants = {
            'n', 'no', 'nope', 'not', '否', '取消',
            '不', '停止', '结束', '退出', '放弃',
            '0', 'false', 'f'
        }
    
    def confirm(self, question: str, default: bool = None,
               hint: str = "[Y/n]") -> bool:
        """
        Y/N 确认提示（核心方法）
        
        这是本模块最常用的方法，提供大小写不敏感的Y/N确认功能。
        
        支持的肯定回答：
        - 英文: y, yes, yep, yeah, ok, okay, true, t, 1
        - 中文: 是, 是的, 好, 好的, 确定, 继续
        
        支持的否定回答：
        - 英文: n, no, nope, not, cancel, false, f, 0
        - 中文: 否, 取消, 不, 停止, 结束, 退出, 放弃
        
        Args:
            question: 确认问题文本（如："是否保存文件？"）
            default: 默认返回值（None表示必须明确选择，True表示默认是，False表示默认否）
            hint: 提示信息（如："[Y/n]" 或 "[y/N]" 表示默认倾向）
            
        Returns:
            bool: True 表示用户确认，False 表示用户否定
            
        Raises:
            无异常，所有错误都会优雅处理
            
        示例:
            >>> prompt = InteractivePrompt()
            
            >>> # 基本用法
            >>> if prompt.confirm("是否继续？"):
            ...     print("用户选择了是")
            >>> else:
            ...     print("用户选择了否")
            
            >>> # 使用默认值（用户直接回车时使用）
            >>> if prompt.confirm("删除文件？", default=False):
            ...     delete_file()  # 仅在用户明确输入Y时执行
            
            >>> # 自定义提示
            >>> prompt.confirm("开始安装？", hint="[Enter=Yes]")
        """
        for attempt in range(self.max_retries + 1):
            try:
                # 构建完整提示文本
                full_question = f"{question} {hint}"
                user_input = input(full_question).strip()
                
                # 记录到历史
                self._record_input('confirm', question, user_input)
                
                # 处理空输入
                if not user_input:
                    if default is not None:
                        return default
                    print(f"  ⚠️ 请输入 Y(是) 或 N(否)")
                    continue
                
                # 规范化并解析输入
                normalized = self._normalize(user_input)
                result = self._parse_yes_no(normalized)
                
                if result is not None:
                    return result
                
                # 输入无法识别，提供反馈
                print(f"  ⚠️ 无法识别 '{user_input}'，请输入 Y(是) 或 N(否)")
                
            except EOFError:
                # 非交互环境（如管道输入）或用户强制终止
                return default if default is not None else False
                
            except KeyboardInterrupt:
                print("\n  ⚠️ 操作已取消")
                return False
        
        # 超过最大重试次数，返回默认值
        return default if default is not None else False
    
    def choose(self, question: str, options: List[str],
              default_index: int = None) -> Optional[str]:
        """
        多选项选择提示
        
        Args:
            question: 选择问题
            options: 选项列表
            default_index: 默认选项索引
            
        Returns:
            选中的选项字符串，或None
        """
        if not options:
            raise ValueError("选项列表不能为空")
        
        option_display = "\n".join(
            f"  [{i+1}] {opt}" for i, opt in enumerate(options)
        )
        
        valid_indices = set(str(i+1) for i in range(len(options)))
        
        for _ in range(self.max_retries + 1):
            try:
                print(f"\n{question}")
                print(option_display)
                
                user_input = input(f"  请选择 [1-{len(options)}]: ").strip()
                self._record_input('choose', question, user_input)
                
                if not user_input:
                    if default_index is not None:
                        return options[default_index]
                    continue
                
                if user_input in valid_indices:
                    return options[int(user_input) - 1]
                
                normalized = self._normalize(user_input)
                for opt in options:
                    if normalized == self._normalize(opt):
                        return opt
                
                print(f"  ⚠️ 无效的选择")
                
            except (EOFError, KeyboardInterrupt):
                return options[default_index] if default_index is not None else None
        
        return options[default_index] if default_index is not None else None
    
    def input_text(self, prompt: str, 
                   validator: Optional[Callable[[str], tuple[bool, str]]] = None,
                   default: str = "",
                   allow_empty: bool = False) -> str:
        """文本输入提示"""
        for _ in range(self.max_retries + 1):
            try:
                user_input = input(f"{prompt}: ").strip()
                self._record_input('text', prompt, user_input)
                
                if not user_input:
                    if allow_empty and default == "":
                        return ""
                    if default:
                        return default
                    continue
                
                if validator:
                    is_valid, message = validator(user_input)
                    if not is_valid:
                        print(f"  ❌ {message}")
                        continue
                
                return user_input
                
            except (EOFError, KeyboardInterrupt):
                return default
        
        return default
    
    def _normalize(self, text: str) -> str:
        """规范化输入文本"""
        if not text:
            return ""
        
        result = text.strip().lower()
        result = re.sub(r'\s+', ' ', result)
        return result
    
    def _parse_yes_no(self, text: str) -> Optional[bool]:
        """解析Y/N输入"""
        if not text:
            return None
        
        normalized = self._normalize(text)
        
        if self._yes_pattern.match(normalized):
            return True
        
        if self._no_pattern.match(normalized):
            return False
        
        if normalized in self._yes_variants:
            return True
        
        if normalized in self._no_variants:
            return False
        
        return None
    
    def _record_input(self, input_type: str, question: str, value: str):
        """记录输入到历史"""
        entry = {
            'type': input_type,
            'question': question,
            'value': value,
            'timestamp': datetime.now().isoformat(),
            'attempt': len([h for h in self.history if h.get('type') == input_type]) + 1
        }
        
        self.history.append(entry)
        
        if len(self.history) > 100:
            self.history = self.history[-100:]
    
    def get_history(self, input_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取输入历史"""
        if input_type:
            return [h for h in self.history if h.get('type') == input_type]
        return list(self.history)
    
    def clear_history(self):
        """清空历史"""
        self.history.clear()


class ConfirmHelper:
    """
    Y/N 确认辅助类（简化版API）
    
    提供更简洁的使用方式，可直接作为函数调用。
    
    示例:
        helper = ConfirmHelper()
        if helper("继续吗？"):
            do_something()
    """
    
    def __init__(self, case_sensitive: bool = False):
        self.prompt = InteractivePrompt(case_insensitive=not case_sensitive)
    
    def __call__(self, question: str, **kwargs) -> bool:
        """快捷调用"""
        return self.prompt.confirm(question, **kwargs)


def confirm(message: str, **kwargs) -> bool:
    """
    全局便捷函数：快速Y/N确认
    
    这是最常用的入口函数，适合简单场景。
    
    Args:
        message: 确认问题
        **kwargs: 其他参数传递给InteractivePrompt.confirm()
        
    Returns:
        bool: 用户的选择
        
    示例:
        >>> from wagent.utils.interactive import confirm
        >>> if confirm("是否继续？"):
        ...     print("继续执行...")
    """
    prompt = InteractivePrompt()
    return prompt.confirm(message, **kwargs)


def ask_choice(question: str, options: List[str], **kwargs) -> Optional[str]:
    """全局便捷函数：多选项选择"""
    prompt = InteractivePrompt()
    return prompt.choose(question, options, **kwargs)


def ask_input(prompt_text: str, **kwargs) -> str:
    """全局便捷函数：文本输入"""
    ip = InteractivePrompt()
    return ip.input_text(prompt_text, **kwargs)