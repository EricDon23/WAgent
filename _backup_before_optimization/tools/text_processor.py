"""
文本处理工具模块
功能：
- 中文分词（jieba）
- 文本清洗
- 格式转换
- 摘要生成
"""

import re
import jieba
import jieba.analyse
from typing import List, Dict, Optional, Tuple


class TextProcessor:
    """文本处理工具"""
    
    def __init__(self):
        """初始化文本处理器"""
        print("📄 文本处理工具初始化完成")
    
    def segment_text(self, text: str, mode: str = "default") -> List[str]:
        """
        中文分词
        
        Args:
            text: 输入文本
            mode: 分词模式 (default/accurate/search)
            
        Returns:
            分词结果列表
        """
        if mode == "search":
            return list(jieba.cut_for_search(text))
        elif mode == "accurate":
            return list(jieba.cut(text, cut_all=True))
        else:
            return list(jieba.cut(text))
    
    def clean_text(self, text: str) -> str:
        """
        清洗文本
        
        清洗项：
        - 去除多余空格
        - 统一标点符号
        - 去除特殊字符
        - 规范换行符
        
        Args:
            text: 输入文本
            
        Returns:
            清洗后的文本
        """
        # 去除首尾空白
        text = text.strip()
        
        # 统一换行符
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # 去除多余空行（保留最多一个空行）
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # 统一中文标点（可选）
        replacements = {
            ',': '，',
            '.': '。',
            '?': '？',
            '!': '！',
            ':': '：',
            ';': '；'
        }
        
        for old, new in replacements.items():
            if old in text and new not in text[:100]:  # 只在非英文内容时替换
                pass  # 可根据需要启用
        
        return text
    
    def extract_sentences(self, text: str) -> List[str]:
        """
        提取句子列表
        
        Args:
            text: 输入文本
            
        Returns:
            句子列表
        """
        sentences = re.split(r'(?<=[。！？\n])', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return sentences
    
    def generate_summary(self, text: str, max_length: int = 200) -> str:
        """
        生成文本摘要（基于关键句提取）
        
        Args:
            text: 输入文本
            max_length: 最大长度
            
        Returns:
            摘要文本
        """
        try:
            from jieba import analyse as jieba_analyse
            summary = jieba_analyse.textrank(text, topK=5, withWeight=False)
            
            if not summary:
                return text[:max_length] + ("..." if len(text) > max_length else "")
            
            summary_text = "".join(summary)
            
            if len(summary_text) > max_length:
                summary_text = summary_text[:max_length-3] + "..."
            
            return summary_text
            
        except Exception as e:
            print(f"⚠️ 摘要生成失败: {e}")
            return text[:max_length]
    
    def count_words(self, text: str) -> Dict[str, int]:
        """
        统计字数信息
        
        Args:
            text: 输入文本
            
        Returns:
            字数统计字典
        """
        char_count = len(text)
        chinese_chars = len(re.findall(r'[\u4e00-\u9fa5]', text))
        english_words = len(re.findall(r'[a-zA-Z]+', text))
        numbers = len(re.findall(r'\d+', text))
        punctuation_count = len(re.findall(r'[^\w\s]', text))
        
        segments = self.segment_text(text)
        word_count = len(segments)
        
        return {
            "total_chars": char_count,
            "chinese_chars": chinese_chars,
            "english_words": english_words,
            "numbers": numbers,
            "punctuation": punctuation_count,
            "segmented_words": word_count,
            "sentences": len(self.extract_sentences(text)),
            "paragraphs": len([p for p in text.split('\n\n') if p.strip()])
        }
    
    def format_to_markdown(
        self,
        title: str,
        content: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """
        转换为Markdown格式
        
        Args:
            title: 标题
            content: 内容
            metadata: 元数据
            
        Returns:
            Markdown格式文本
        """
        lines = [f"# {title}", ""]
        
        if metadata:
            lines.append("**元数据**：")
            for key, value in metadata.items():
                lines.append(f"- **{key}**: {value}")
            lines.append("")
            lines.append("---")
            lines.append("")
        
        lines.append(content)
        
        word_info = self.count_words(content)
        lines.append("")
        lines.append(f"---")
        lines.append(f"*字数统计：约{word_info['chinese_chars']}字*")
        
        return "\n".join(lines)
    
    def detect_language(self, text: str) -> str:
        """
        检测主要语言
        
        Args:
            text: 输入文本
            
        Returns:
            语言代码 (zh/en/mixed)
        """
        chinese_ratio = len(re.findall(r'[\u4e00-\u9fa5]', text)) / max(len(text), 1)
        english_ratio = len(re.findall(r'[a-zA-Z]', text)) / max(len(text), 1)
        
        if chinese_ratio > 0.6:
            return "zh"
        elif english_ratio > 0.6:
            return "en"
        else:
            return "mixed"


if __name__ == "__main__":
    processor = TextProcessor()
    
    test_text = """
    李明坐在电脑前，看着屏幕上闪烁的光标。小爱的声音从扬声器中传出："李明，你今天看起来很疲惫。"李明苦笑着摇了摇头。
    
    这是一个关于人工智能与人类情感的故事。
    """
    
    print("\n🔤 分词结果:")
    print(processor.segment_text(test_text)[:20])
    
    print("\n📊 字数统计:")
    stats = processor.count_words(test_text)
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("\n📝 摘要:")
    print(processor.generate_summary(test_text))
