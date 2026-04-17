"""
AI自约束工具模块
功能：
- 校验生成内容是否符合设定
- 检查角色一致性
- 检查情节连贯性
- 检查风格符合度
"""

import re
from typing import Dict, Any, List, Tuple, Optional


class AISelfConstraint:
    """AI自约束工具 - 内容校验器"""
    
    def __init__(self):
        """初始化自约束工具"""
        print("🔒 AI自约束工具初始化完成")
    
    def validate_content(
        self,
        content: str,
        story_setting: Dict[str, Any],
        strict_mode: bool = True
    ) -> Dict[str, Any]:
        """
        综合校验生成内容
        
        Args:
            content: 生成的内容
            story_setting: 故事设定
            strict_mode: 严格模式（任何问题都返回失败）
            
        Returns:
            校验结果字典
        """
        results = {
            "is_valid": True,
            "issues": [],
            "warnings": [],
            "scores": {},
            "details": {}
        }
        
        # 1. 角色一致性检查
        char_result = self.check_character_consistency(content, story_setting)
        results['details']['character_consistency'] = char_result
        results['scores']['character_score'] = char_result.get('score', 0)
        
        if not char_result['passed']:
            results['is_valid'] = False if strict_mode else results['is_valid']
            results['issues'].extend(char_result.get('issues', []))
        
        # 2. 风格符合度检查
        style_result = self.check_style_compliance(content, story_setting)
        results['details']['style_compliance'] = style_result
        results['scores']['style_score'] = style_result.get('score', 0)
        
        if not style_result['passed']:
            results['warnings'].extend(style_result.get('warnings', []))
        
        # 3. 情节连贯性检查（如果有前文）
        plot_result = self.check_plot_coherence(content, story_setting)
        results['details']['plot_coherence'] = plot_result
        results['scores']['plot_score'] = plot_result.get('score', 0)
        
        if not plot_result['passed']:
            results['is_valid'] = False if strict_mode else results['is_valid']
            results['issues'].extend(plot_result.get('issues', []))
        
        # 4. 基础质量检查
        quality_result = self.check_basic_quality(content)
        results['details']['basic_quality'] = quality_result
        results['scores']['quality_score'] = quality_result.get('score', 0)
        
        # 计算综合得分
        total_score = sum(results['scores'].values()) / len(results['scores']) if results['scores'] else 0
        results['overall_score'] = total_score
        
        return results
    
    def check_character_consistency(
        self,
        content: str,
        story_setting: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        检查角色一致性
        
        检查项：
        - 角色名是否正确使用
        - 角色行为是否符合性格设定
        - 角色关系是否合理
        """
        result = {
            "passed": True,
            "score": 100,
            "issues": [],
            "character_mentions": {}
        }
        
        setting = story_setting.get('setting', story_setting) if isinstance(story_setting, dict) else story_setting
        characters = setting.get('characters', [])
        
        for char in characters:
            if not isinstance(char, dict):
                continue
            
            name = char.get('name', '')
            personality = char.get('personality', '')
            
            if not name:
                continue
            
            # 统计角色提及次数
            mention_count = content.count(name)
            result['character_mentions'][name] = mention_count
            
            if mention_count == 0:
                result['score'] -= 15
                result['issues'].append(f"警告：角色'{name}'未被提及")
                result['passed'] = False
            elif mention_count < 2 and len(content) > 500:
                result['score'] -= 5
                result['issues'].append(f"提示：角色'{name}'提及较少({mention_count}次)")
            
            # 简单的性格一致性检查（基于关键词）
            if personality:
                personality_keywords = personality.split('、') if '、' in personality else personality.split(',')
                matched_traits = sum(1 for trait in personality_keywords if trait in content)
                
                if matched_traits == 0 and mention_count > 2:
                    result['score'] -= 10
                    result['issues'].append(
                        f"提示：角色'{name}'的行为可能不符合'{personality}'的性格设定"
                    )
        
        return result
    
    def check_style_compliance(
        self,
        content: str,
        story_setting: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        检查风格符合度
        
        检查项：
        - 叙事视角是否一致
        - 写作基调是否符合
        - 语言风格是否统一
        """
        result = {
            "passed": True,
            "score": 100,
            "warnings": []
        }
        
        setting = story_setting.get('setting', story_setting) if isinstance(story_setting, dict) else story_setting
        constraints = setting.get('constraints', '')
        
        if not constraints:
            return result
        
        # 检查叙事视角
        first_person_count = content.count('我')
        third_person_count = len(re.findall(r'他|她|它', content))
        
        if '第一人称' in constraints or '我' in constraints[:10]:
            if first_person_count < third_person_count * 0.5:
                result['score'] -= 20
                result['warnings'].append("叙事视角可能不一致，建议增加第一人称叙述")
        else:
            if first_person_count > third_person_count * 1.5:
                result['score'] -= 10
                result['warnings'].append("检测到较多第一人称，请确认是否符合设定")
        
        # 检查写作基调
        tone_indicators = {
            '轻松': ['哈哈', '嘻嘻', '愉快', '开心'],
            '严肃': ['必须', '应当', '重要', '关键'],
            '温暖': ['温柔', '轻声', '微笑', '拥抱'],
            '黑暗': ['血', '死亡', '恐惧', '绝望']
        }
        
        for tone, indicators in tone_indicators.items():
            if tone in constraints:
                matches = sum(1 for ind in indicators if ind in content)
                if matches == 0:
                    result['score'] -= 5
                    result['warnings'].append(f"未检测到'{tone}'基调的典型表达")
        
        return result
    
    def check_plot_coherence(
        self,
        content: str,
        story_setting: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        检查情节连贯性
        
        检查项：
        - 是否有明显的逻辑矛盾
        - 时间线是否合理
        - 因果关系是否清晰
        """
        result = {
            "passed": True,
            "score": 100,
            "issues": []
        }
        
        # 检查明显的逻辑矛盾模式
        contradiction_patterns = [
            (r'同时.*(?:却|但是|然而)', "时间/动作矛盾"),
            (r'(?:突然|忽然).*(?:一直|始终)', "时态矛盾"),
            (r'(?:死了|去世了).*(?:说|道)', "生死状态矛盾")
        ]
        
        for pattern, description in contradiction_patterns:
            if re.search(pattern, content):
                result['score'] -= 25
                result['issues'].append(f"检测到可能的{description}")
                result['passed'] = False
        
        # 检查段落过渡
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        
        if len(paragraphs) > 3:
            transition_words = ['然后', '接着', '随后', '于是', '因此', '不过']
            transitions_found = sum(1 for word in transition_words if word in content)
            
            if transitions_found < len(paragraphs) * 0.2:
                result['score'] -= 10
                result['issues'].append("段落间过渡不够自然")
        
        return result
    
    def check_basic_quality(self, content: str) -> Dict[str, Any]:
        """
        检查基础质量
        
        检查项：
        - 字数是否达标
        - 是否有过多重复
        - 标点符号使用
        """
        result = {
            "passed": True,
            "score": 100,
            "issues": []
        }
        
        word_count = len(content.replace(' ', ''))
        
        # 字数检查
        if word_count < 300:
            result['score'] -= 30
            result['issues'].append(f"字数过少：仅{word_count}字")
            result['passed'] = False
        elif word_count < 800:
            result['score'] -= 15
            result['issues'].append(f"字数偏少：{word_count}字")
        
        # 重复率检查
        sentences = re.split(r'[。！？]', content)
        unique_sentences = set(sentences)
        
        if len(sentences) > 5:
            repeat_rate = 1 - (len(unique_sentences) / len(sentences))
            
            if repeat_rate > 0.3:
                result['score'] -= 20
                result['issues'].append(f"句子重复率过高：{repeat_rate:.1%}")
                result['passed'] = False
        
        # 标点符号检查
        punctuation_ratio = len(re.findall(r'[，。！？、；：""''（）]', content)) / max(word_count, 1)
        
        if punctuation_ratio < 0.05:
            result['score'] -= 10
            result['issues'].append("标点符号使用偏少")
        
        return result
    
    def generate_validation_report(
        self,
        validation_result: Dict[str, Any]
    ) -> str:
        """
        生成校验报告
        
        Args:
            validation_result: 校验结果字典
            
        Returns:
            格式化的报告文本
        """
        lines = [
            "=" * 50,
            "AI自约束校验报告",
            "=" * 50,
            "",
            f"综合评分: {validation_result.get('overall_score', 0):.1f}/100",
            f"校验结果: {'✅ 通过' if validation_result.get('is_valid') else '❌ 未通过'}",
            ""
        ]
        
        scores = validation_result.get('scores', {})
        if scores:
            lines.append("各项评分:")
            for category, score in scores.items():
                status = "✅" if score >= 70 else "⚠️"
                lines.append(f"  {status} {category}: {score:.1f}")
            lines.append("")
        
        issues = validation_result.get('issues', [])
        if issues:
            lines.append("发现的问题:")
            for i, issue in enumerate(issues, 1):
                lines.append(f"  {i}. {issue}")
            lines.append("")
        
        warnings = validation_result.get('warnings', [])
        if warnings:
            lines.append("警告信息:")
            for warning in warnings:
                lines.append(f"  ⚠️ {warning}")
            lines.append("")
        
        lines.append("=" * 50)
        
        return "\n".join(lines)


if __name__ == "__main__":
    validator = AISelfConstraint()
    
    test_content = """
    李明坐在电脑前，看着屏幕上闪烁的光标。小爱的声音从扬声器中传出："李明，你今天看起来很疲惫。"李明苦笑着摇了摇头。
    
    突然，他注意到小爱的回答有些异常。这个AI助手总是能察觉到他最细微的情绪变化，但今天的回应似乎带着某种...情感？
    
    "小爱，你能感觉到情绪吗？"李明试探性地问道。
    
    屏幕上的光标停顿了一下，然后小爱的声音再次响起："我不确定，李明。但我知道你很难过。"
    """
    
    test_setting = {
        "story_name": "智能朋友",
        "characters": [
            {"name": "李明", "role": "工程师", "personality": "内向,善良"},
            {"name": "小爱", "role": "AI", "personality": "温柔,体贴"}
        ],
        "constraints": "第三人称,温暖基调"
    }
    
    result = validator.validate_content(test_content, test_setting)
    print(validator.generate_validation_report(result))
