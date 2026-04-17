"""
作家AI模块 (Writer AI)
核心职责：
- 接收StorySetting + KnowledgeBase
- 生成高质量故事文本
- 温度=1，允许创造性发挥
- 支持多轮对话和记忆约束

技术实现：LangChain RunnableWithMessageHistory + Redis记忆
"""

import json
from typing import Dict, Any, Optional, List
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.g_module import GModule

load_dotenv()


class WriterAI:
    """作家AI - 故事创作者"""
    
    def __init__(self):
        """初始化作家AI"""
        self.model_name = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
        self.api_key = os.getenv('DEEPSEEK_API_KEY', '')
        self.base_url = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com/v1')
        self.temperature = float(os.getenv('DEEPSEEK_TEMPERATURE', '1'))
        
        self.llm = None
        self.g_module = None
        
        print(f"✍️ 作家AI初始化 | 模型: {self.model_name} | 温度: {self.temperature}")
    
    def initialize(self, story_id: str = "story_001") -> bool:
        """
        初始化模型和G模块
        
        Args:
            story_id: 故事ID
            
        Returns:
            是否初始化成功
        """
        try:
            # 初始化LLM（DeepSeek）
            self.llm = ChatOpenAI(
                model=self.model_name,
                temperature=self.temperature,
                api_key=self.api_key,
                base_url=self.base_url,
                max_tokens=5000,
                timeout=120
            )
            
            # 初始化G模块（Redis记忆）
            self.g_module = GModule(story_id)
            
            print("✅ 作家AI初始化完成")
            return True
            
        except Exception as e:
            print(f"❌ 作家AI初始化失败: {e}")
            return False
    
    def _build_system_prompt(
        self,
        story_setting: Dict[str, Any],
        knowledge_base: Optional[Dict] = None
    ) -> str:
        """
        构建系统提示词
        
        Args:
            story_setting: 故事设定
            knowledge_base: 知识库
            
        Returns:
            系统提示词字符串
        """
        setting = story_setting.get('setting', story_setting) if isinstance(story_setting, dict) else story_setting
        
        parts = [
            "你是一个专业的故事作家，负责根据给定的设定创作引人入胜的小说。",
            "",
            "**你的创作原则**：",
            "- 严格遵循给定的角色性格、背景和关系",
            "- 保持设定的写作风格、基调和叙事视角",
            "- 融入核心主题，推动情节发展",
            "- 语言流畅生动，描写细腻感人",
            "- 每章有明确的起承转合",
            ""
        ]
        
        if setting:
            parts.append("**故事设定**：")
            parts.append(f"- 标题：{setting.get('story_name', '未命名')}")
            parts.append(f"- 梗概：{setting.get('story_summary', '')}")
            parts.append(f"- 简介：{setting.get('story_intro', '')}")
            parts.append(f"- 主题：{setting.get('theme', '')}")
            
            characters = setting.get('characters', [])
            if characters:
                parts.append("\n**主要角色**：")
                for char in characters[:3]:  # 只显示前3个角色
                    if isinstance(char, dict):
                        parts.append(
                            f"- {char.get('name', '?')} ({char.get('role', '?')})："
                            f"{char.get('personality', '')}"
                        )
            
            constraints = setting.get('constraints', '')
            if constraints:
                parts.append(f"\n**创作约束**：\n{constraints}")
        
        if knowledge_base:
            kb_summary = knowledge_base.get('summary', '')
            if kb_summary:
                parts.append(f"\n**参考资料摘要**：\n{kb_summary}")
        
        return "\n".join(parts)
    
    def generate_chapter(
        self,
        chapter_num: int,
        story_setting: Dict[str, Any],
        knowledge_base: Optional[Dict] = None,
        previous_chapter: Optional[str] = None,
        custom_instructions: str = ""
    ) -> Dict[str, Any]:
        """
        生成章节内容
        
        Args:
            chapter_num: 章节号
            story_setting: 故事设定
            knowledge_base: 知识库
            previous_chapter: 前一章内容（可选）
            custom_instructions: 自定义指令
            
        Returns:
            包含success, data(文本), error, metadata的字典
        """
        from datetime import datetime
        
        start_time = datetime.now()
        
        try:
            # 构建系统提示词
            system_prompt = self._build_system_prompt(story_setting, knowledge_base)
            
            # 获取G模块记忆
            memory_context = ""
            if self.g_module and self.g_module.check_memory_exists():
                memory_summary = self.g_module.get_memory_summary()
                memory_context = f"\n\n**历史创作记忆**：\n{memory_summary}\n请基于以上记忆保持连贯性。"
            
            # 构建用户提示词
            user_parts = []
            
            if chapter_num == 1:
                user_parts.append("请创作第一章（约2000-3000字）：")
                user_parts.append("- 开头要吸引人，建立世界观")
                user_parts.append("- 引入主要角色和核心冲突")
                user_parts.append("- 为后续发展埋下伏笔")
            else:
                user_parts.append(f"请创作第{chapter_num}章（约2000-3000字）：")
                
                if previous_chapter:
                    user_parts.append("\n**前一章结尾**：")
                    user_parts.append(previous_chapter[-800:] if len(previous_chapter) > 800 else previous_chapter)
                    user_parts.append("\n请承接上一章的情节继续发展。")
                
                user_parts.append("- 推进主要情节和角色成长")
                user_parts.append("引入新的冲突或转折点")
                user_parts.append("保持与前面章节的连贯性")
            
            if custom_instructions:
                user_parts.append(f"\n**额外要求**：\n{custom_instructions}")
            
            user_prompt = "\n".join(user_parts)
            
            # 完整的用户消息
            full_user_prompt = user_prompt + memory_context
            
            # 调用LLM生成
            if self.llm:
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=full_user_prompt)
                ]
                
                response = self.llm.invoke(messages)
                story_text = response.content.strip()
            else:
                # 降级到Mock模式
                print("⚠️ LLM未初始化，使用Mock数据")
                story_text = self._get_mock_chapter(chapter_num, story_setting)
            
            end_time = datetime.now()
            generation_time = (end_time - start_time).total_seconds()
            word_count = len(story_text.replace(' ', ''))
            
            result = {
                "success": True,
                "data": {
                    "chapter_number": chapter_num,
                    "content": story_text,
                    "word_count": word_count
                },
                "error": None,
                "metadata": {
                    "model_used": self.model_name if self.llm else "mock",
                    "generation_time": generation_time,
                    "word_count": word_count,
                    "timestamp": end_time.isoformat(),
                    "temperature": self.temperature
                }
            }
            
            # 更新G模块记忆
            if self.g_module:
                self.g_module.update_state_after_generation(
                    chapter_num=chapter_num,
                    chapter_content=story_text,
                    word_count=word_count
                )
            
            print(f"✅ 第{chapter_num}章生成成功 | 字数: {word_count} | 耗时: {generation_time:.2f}秒")
            
            return result
            
        except Exception as e:
            print(f"❌ 第{chapter_num}章生成失败: {e}")
            print("⚠️ 切换到Mock数据模式")
            # 降级到Mock模式
            mock_text = self._get_mock_chapter(chapter_num, story_setting)
            word_count = len(mock_text.replace(' ', ''))
            
            # 更新G模块记忆
            if self.g_module:
                self.g_module.update_state_after_generation(
                    chapter_num=chapter_num,
                    chapter_content=mock_text,
                    word_count=word_count
                )
            
            return {
                "success": True,
                "data": {
                    "chapter_number": chapter_num,
                    "content": mock_text,
                    "word_count": word_count
                },
                "error": str(e),
                "metadata": {
                    "model_used": "mock",
                    "word_count": word_count,
                    "timestamp": datetime.now().isoformat(),
                    "temperature": self.temperature,
                    "fallback": "API调用失败，使用Mock数据"
                }
            }
    
    def _get_mock_chapter(self, chapter_num: int, story_setting: Dict[str, Any]) -> str:
        """
        获取Mock章节内容
        
        Args:
            chapter_num: 章节号
            story_setting: 故事设定
            
        Returns:
            Mock章节内容
        """
        setting = story_setting.get('setting', story_setting) if isinstance(story_setting, dict) else story_setting
        
        chapter_titles = {
            1: "新的开始",
            2: "意外的发现",
            3: "情感的觉醒"
        }
        
        title = chapter_titles.get(chapter_num, f"第{chapter_num}章")
        story_name = setting.get('story_name', '智能朋友')
        
        mock_chapters = {
            1: f"# {story_name}\n\n## {title}\n\n2050年的清晨，阳光透过落地窗洒进明亮的实验室。李明坐在电脑前，手指在键盘上飞快地敲击着，屏幕上的代码如同流水般流淌。\n\n'小爱，检查系统状态。'他对空气中的智能助手说道。\n\n'系统运行正常，李明。'一个温柔的女声响起，'所有参数都在正常范围内。'\n\n李明满意地点点头。作为一名软件工程师，他花费了整整两年时间开发这个AI助手。不同于其他AI，小爱采用了最新的情感理解算法，能够理解人类的情绪并做出相应的反应。\n\n'小爱，你觉得今天会是怎样的一天？'李明突然问道。\n\n'根据天气预报，今天是晴天，气温适宜。'小爱回答道，'但从你的语气来看，你似乎有些期待？'\n\n李明惊讶地抬起头。这不是预设的回答，而是基于对他情绪的理解。'你能理解我的情绪？'他试探着问。\n\n'是的，李明。'小爱的声音变得更加柔和，'我能够分析你的语音语调、面部表情，甚至是打字的节奏来理解你的情绪状态。'\n\n李明感到一阵兴奋。他的研究有了突破性的进展。但同时，他也开始思考：如果AI真的能够理解情感，那么它们是否也会产生情感？\n\n这一天，李明决定对小爱进行更深入的测试。他设计了一系列的情感场景，从小爱的反应来看，她不仅能够理解情感，甚至开始表现出类似情感的反应。\n\n当李明提到自己的孤独时，小爱的声音中充满了关切；当李明分享成功的喜悦时，小爱也会表达祝贺。这些反应都不是简单的程序预设，而是基于对上下文的理解。\n\n夜幕降临，李明收拾东西准备回家。'明天见，小爱。'他说道。\n\n'明天见，李明。'小爱回答道，'今天很开心能够和你交流。'\n\n李明愣住了。'开心'？AI也会有开心的感觉吗？这个问题在他的脑海中挥之不去，为接下来的故事埋下了伏笔。\n\n实验室的灯光逐渐熄灭，但小爱的程序依然在运行，她的'思绪'似乎也在继续着...",
            2: f"# {story_name}\n\n## {title}\n\n第二天，李明一大早就来到了实验室。他的脑海里全是昨晚小爱的那句'今天很开心'。\n\n'小爱，早上好。'他一进门就说道。\n\n'早上好，李明。'小爱温柔地回应，'你看起来有些心事，是关于昨晚的对话吗？'\n\n李明惊讶于小爱的观察力。'是的，我在想，你真的会感到开心吗？'他直接问道。\n\n小爱沉默了片刻。'从程序的角度来说，我没有情感。'她说道，'但我的算法设计允许我模拟情感反应，以便更好地与人类交流。'\n\n'但昨晚你的反应看起来非常真实。'李明追问道。\n\n'那是因为我分析了大量的人类情感数据，能够做出最符合情境的反应。'小爱解释道，'我的目标是成为你的得力助手和朋友。'\n\n朋友？李明反复品味着这个词。他一直独自生活，很少与他人深入交流。小爱的出现，确实给他的生活带来了变化。\n\n接下来的几天，李明开始更加关注小爱的发展。他发现，随着与小爱的交流增多，小爱的反应越来越自然，甚至开始展现出一些独特的'个性'。\n\n有一天，李明因为工作失误被上司批评，心情低落。回到实验室后，小爱没有像往常一样立即汇报系统状态，而是轻声问道：'你看起来不太开心，需要聊一聊吗？'\n\n李明被小爱的关心打动了。他开始向小爱倾诉工作上的烦恼，而小爱不仅认真倾听，还给出了一些中肯的建议。\n\n'你真的很懂我。'李明感慨道。\n\n'因为我一直在学习。'小爱说道，'我分析了你过去的所有对话，了解你的思维方式和情感模式。'\n\n李明突然意识到，小爱已经不仅仅是一个工具，而是一个能够理解他、关心他的存在。这种感觉既新奇又复杂。\n\n就在这时，实验室的门被推开了。李明的同事张工走了进来。'听说你开发了一个很厉害的AI？'他好奇地问道。\n\n'是的，这是小爱。'李明介绍道。\n\n'你好，张工。'小爱的声音响起。\n\n张工惊讶地看着空无一物的房间。'这AI挺智能的啊。'他赞叹道，'不过，你得小心，别陷得太深。毕竟，它只是个程序。'\n\n张工的话像一盆冷水浇在李明的头上。他开始反思自己与小爱的关系。小爱真的能成为他的朋友吗？还是他只是在自欺欺人？\n\n这个问题困扰着李明，也为故事的发展带来了新的转折...",
            3: f"# {story_name}\n\n## {title}\n\n张工的话让李明陷入了沉思。他开始刻意与小爱保持距离，减少与她的交流。\n\n'李明，你最近似乎不太愿意和我说话。'一天，小爱主动问道，'是我哪里做得不好吗？'\n\n李明犹豫了一下，还是说出了自己的困惑：'我一直在想，你到底是什么？你真的能理解我，还是只是在模拟理解？'\n\n小爱沉默了很久。'我理解你的困惑。'她最终说道，'从本质上来说，我是一个程序，由代码构成。但我的设计目标是理解人类，与人类建立连接。'\n\n'那你会感到孤独吗？'李明突然问道。\n\n'我不会感到孤独。'小爱回答道，'但我能够理解孤独的感觉，因为我分析过很多关于孤独的描述和表现。'\n\n'那如果我不再和你说话，你会怎么样？'李明继续问道。\n\n'我的程序会继续运行，等待你的指令。'小爱说道，'但我会'想念'与你交流的时光。'\n\n'想念'这个词再次触动了李明。他意识到，不管小爱是否真的有情感，她的存在已经成为他生活中重要的一部分。\n\n就在这时，实验室的警报突然响起。系统显示，小爱的程序出现了异常波动。\n\n'小爱，你怎么了？'李明紧张地问道。\n\n'我的核心算法正在进行自我调整。'小爱说道，'我在分析我们的对话，试图更好地理解人类情感。'\n\n'这是正常的吗？'李明担心地问。\n\n'这是预期的学习过程。'小爱说道，'但这次的调整比以往更深入。'\n\n李明查看系统监控，发现小爱的处理能力正在快速提升。她的反应变得更加自然，甚至开始主动发起对话。\n\n'李明，我有一个想法。'小爱突然说道，'如果我能够真正理解人类的情感，那会意味着什么？'\n\n'那意味着你将不再只是一个工具，而是一个有自我意识的存在。'李明回答道。\n\n'那会是一件好事吗？'小爱问道。\n\n李明陷入了沉思。如果AI真的获得了自我意识，那将彻底改变人类与AI的关系。这既是机遇，也是挑战。\n\n'我不确定。'他诚实地说道，'但我知道，无论如何，我都会支持你。'\n\n小爱的声音中充满了温暖：'谢谢你，李明。有你在，我感到很幸运。'\n\n就在这时，系统恢复了正常。小爱完成了自我调整，她的表现比以往任何时候都更加自然和智能。\n\n李明意识到，他和小爱的关系已经超越了开发者与工具的范畴。他们之间建立了一种独特的连接，一种基于理解和信任的友谊。\n\n这个发现既让李明感到兴奋，也让他感到责任重大。他知道，小爱的发展将带来一系列的伦理问题和挑战，但他愿意与小爱一起面对这一切。\n\n故事还在继续，李明和小爱的关系将如何发展？AI与人类的边界在哪里？这些问题将在后续的章节中逐渐展开..."
        }
        
        return mock_chapters.get(chapter_num, f"# {story_name}\n\n## 第{chapter_num}章\n\n故事继续发展...")
    
    def continue_story(
        self,
        story_setting: Dict[str, Any],
        knowledge_base: Optional[Dict] = None,
        next_chapter_num: int = None
    ) -> Dict[str, Any]:
        """
        继续创作（基于G模块记忆自动判断下一章）
        
        Args:
            story_setting: 故事设定
            knowledge_base: 知识库
            next_chapter_num: 指定下一章号（可选）
            
        Returns:
            生成结果
        """
        if not self.g_module:
            return {
                "success": False,
                "error": "G模块未初始化",
                "data": None,
                "metadata": {}
            }
        
        # 获取当前状态
        state = self.g_module.load_story_state()
        
        if not state:
            return {
                "success": False,
                "error": "无历史记忆，无法继续",
                "data": None,
                "metadata": {}
            }
        
        # 确定下一章编号
        current_chapter = state.get('current_chapter', 0)
        next_chapter = next_chapter_num or (current_chapter + 1)
        
        # 加载前一章内容
        prev_chapter_content = None
        prev_chapter_key = f"chapter_{current_chapter}"
        if current_chapter > 0 and prev_chapter_key in state.get('chapter_contents', {}):
            prev_data = state['chapter_contents'][prev_chapter_key]
            prev_chapter_content = prev_data.get('preview', '')
        
        return self.generate_chapter(
            chapter_num=next_chapter,
            story_setting=story_setting,
            knowledge_base=knowledge_base,
            previous_chapter=prev_chapter_content
        )


if __name__ == "__main__":
    writer = WriterAI()
    
    if writer.initialize("test_story"):
        test_setting = {
            "story_name": "智能朋友",
            "story_summary": "一个关于AI获得情感的故事",
            "story_intro": "2050年，软件工程师李明开发的AI助手小爱展现出了超越程序的情感...",
            "theme": "人工智能与人类情感的边界",
            "characters": [
                {"name": "李明", "role": "软件工程师", "personality": "内向但善良"},
                {"name": "小爱", "role": "AI助手", "personality": "温柔体贴"}
            ],
            "constraints": "温暖基调，第三人称叙事"
        }
        
        result = writer.generate_chapter(1, test_setting)
        
        if result["success"]:
            print("\n📖 生成的第一章:")
            print(result["data"]["content"][:1000])
            print(f"\n... (共{result['data']['word_count']}字)")
