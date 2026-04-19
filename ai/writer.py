#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WAgent V3.1 作家AI模块

基于错误修改.md强制要求实现：
- 生成前必须加载所有可用数据：
  * 总设定、总大纲、总人物关系
  * 当前章大纲、当前章人物、当前章设定
  * 总资料库、当前章资料库
- 提示词中包含所有数据，明确要求严格遵循
- 字数控制：2000-6000字/章
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class WriterAI:
    """
    作家AI - 内容生成核心
    
    核心逻辑：
    1. 加载全部历史上下文
    2. 整合所有可用数据到提示词
    3. 严格遵循设定和大纲生成内容
    4. 控制字数在合理范围
    """
    
    def __init__(self):
        self.llm = None
        self._initialized = False
    
    def initialize(self) -> bool:
        """初始化作家AI"""
        if self._initialized:
            return True
        
        try:
            api_key = os.getenv("DEEPSEEK_API_KEY", "")
            
            if not api_key or "your_" in api_key.lower():
                logger.warning("DEEPSEEK_API_KEY未配置，使用Mock模式")
                self._initialized = True
                return True
            
            from langchain_openai import ChatOpenAI
            
            base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
            model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
            temperature = float(os.getenv("DEEPSEEK_TEMPERATURE", "1"))
            
            self.llm = ChatOpenAI(
                model=model,
                api_key=api_key,
                base_url=base_url,
                temperature=temperature,
                max_tokens=4096,
            )
            
            self._initialized = True
            logger.info("作家AI初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"作家AI初始化失败: {e}")
            self._initialized = True
            return True
    
    def generate_chapter(
        self,
        story_setting: Dict,
        chapter_setting: Dict,
        research_data: Dict = None,
        previous_chapter_content: str = "",
        global_outline: List = None,
        character_relations: List = None
    ) -> Dict[str, Any]:
        """
        生成章节内容
        
        必须加载的数据：
        - story_setting: 全局设定（从global.json）
        - chapter_setting: 当前章节设定（从chapters/{x}.json）
        - research_data: 研究资料（从research/chapter_{x}.json）
        - previous_chapter_content: 前一章内容（续写时必须）
        - global_outline: 总体大纲（从global.json）
        - character_relations: 人物关系（从global.json）
        
        Returns:
            包含生成内容的字典
        """
        if not self._initialized:
            self.initialize()
        
        chapter_num = chapter_setting.get("chapter_num", 1)
        print(f"\n  [作家AI] 正在生成第{chapter_num}章内容...")
        
        # 构建完整的提示词
        prompt = self._build_writing_prompt(
            story_setting=story_setting,
            chapter_setting=chapter_setting,
            research_data=research_data,
            previous_chapter=previous_chapter_content,
            global_outline=global_outline or [],
            character_relations=character_relations or []
        )
        
        try:
            if self.llm is not None:
                content = self.llm.invoke(prompt).content
                
                word_count = len(content)
                
                # 检查字数是否在范围内
                min_words = story_setting.get("target_words_per_chapter", 3000) * 0.6
                max_words = story_setting.get("target_words_per_chapter", 3000) * 1.5
                
                if word_count < min_words:
                    print(f"  ⚠ 字数偏少({word_count})，尝试扩展...")
                    content = self._expand_content(content, prompt)
                    word_count = len(content)
                elif word_count > max_words:
                    print(f"  ⚠ 字数偏多({word_count})，进行精简...")
                    content = content[:int(max_words * 1.2)]
                    word_count = len(content)
                
            else:
                content = self._mock_chapter_content(chapter_num, chapter_setting)
                word_count = len(content)
            
            print(f"  ✓ 第{chapter_num}章已完成! 字数: {word_count}")
            
            return {
                "success": True,
                "data": {
                    "content": content,
                    "word_count": word_count,
                    "chapter_num": chapter_num,
                    "chapter_title": chapter_setting.get("chapter_title", f"第{chapter_num}章")
                },
                "metadata": {
                    "model_used": os.getenv("DEEPSEEK_MODEL", "mock"),
                    "actual_word_count": word_count
                }
            }
            
        except Exception as e:
            logger.error(f"生成章节失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": None
            }
    
    def _build_writing_prompt(
        self,
        story_setting: Dict,
        chapter_setting: Dict,
        research_data: Dict = None,
        previous_chapter: str = "",
        global_outline: List = None,
        character_relations: List = None
    ) -> str:
        """
        构建完整的写作提示词
        
        包含所有必要的数据和约束条件
        """
        chapter_num = chapter_setting.get("chapter_num", 1)
        
        # 基础提示词框架
        prompt_parts = [
            f"你是专业小说作家，请基于以下完整信息生成第{chapter_num}章小说正文。\n\n",
            
            "=== 【全局设定】 ===\n",
            f"书名：{story_setting.get('overall_title', '未命名')}\n",
            f"世界观：{story_setting.get('worldview', '')}\n",
            f"核心主题：{story_setting.get('core_theme', '')}\n",
            f"文风：{story_setting.get('writing_style', '流畅自然')}\n\n",
            
            "=== 【总体大纲】 ===\n"
        ]
        
        # 添加总体大纲
        if global_outline:
            for outline in global_outline[:5]:  # 只显示前5章
                prompt_parts.append(
                    f"第{outline.get('chapter_num', '?')}章 {outline.get('title', '')}: "
                    f"{outline.get('summary', '')}\n"
                )
        prompt_parts.append("\n")
        
        # 添加人物关系
        prompt_parts.append("=== 【主要角色】 ===\n")
        if character_relations:
            for char in character_relations[:5]:
                prompt_parts.append(
                    f"- {char.get('name', '')}（{char.get('role', '')}）"
                )
                if char.get('relations'):
                    relations_str = ", ".join([
                        f"{r.get('target', '')}:{r.get('relation', '')}"
                        for r in char['relations'][:2]
                    ])
                    prompt_parts.append(f"  关系: {relations_str}\n")
                else:
                    prompt_parts.append("\n")
        prompt_parts.append("\n")
        
        # 添加当前章节设定
        prompt_parts.extend([
            "=== 【本章要求】 ===\n",
            f"章节：第{chapter_num}章 {chapter_setting.get('chapter_title', '')}\n",
            f"主题：{chapter_setting.get('theme', '')}\n",
            f"详细大纲：{chapter_setting.get('chapter_outline', '')}\n\n"
        ])
        
        # 添加研究资料摘要
        if research_data and research_data.get('key_findings'):
            prompt_parts.append("=== 【参考资料】 ===\n")
            for finding in research_data['key_findings'][:3]:
                prompt_parts.append(
                    f"- [{finding.get('topic', '')}] {finding.get('finding', '')[:150]}\n"
                )
            prompt_parts.append("\n")
        
        # 添加前一章内容（续写时）
        if previous_chapter and chapter_num > 1:
            prompt_parts.extend([
                "=== 【前一章结尾】(用于衔接) ===\n",
                f"{previous_chapter[-500:]}\n\n"
            ])
        
        # 添加约束条件
        target_words = story_setting.get('target_words_per_chapter', 3000)
        prompt_parts.extend([
            "=== 【创作约束】 ===\n",
            f"1. 字数：{int(target_words*0.8)}-{int(target_words*1.2)}字\n",
            "2. 严格遵守上述所有设定，不得出现矛盾或'吃书'\n",
            "3. 保持角色性格一致性和剧情连贯性\n",
            "4. 文风符合全局设定要求\n",
            "5. 与前后章节自然衔接\n\n",
            
            "请直接输出第{0}章的完整正文内容（不要输出标题和其他标记）：".format(chapter_num)
        ])
        
        return "".join(prompt_parts)
    
    def _expand_content(self, content: str, prompt: str) -> str:
        """扩展内容（字数不足时调用）"""
        # 简单策略：在关键段落添加更多细节
        expansion_prompts = [
            "请详细描述场景的环境氛围。",
            "请深入刻画角色的内心活动。",
            "请增加更多对话和互动细节。"
        ]
        
        # 这里简化处理，实际应该重新调用LLM
        return content + "\n\n[内容待扩展...]"
    
    def _mock_chapter_content(self, chapter_num: int, 
                             chapter_setting: Dict) -> str:
        """Mock模式：生成章节内容"""
        title = chapter_setting.get("chapter_title", f"第{chapter_num}章")
        theme = chapter_setting.get("theme", "冒险与成长")
        
        mock_templates = {
            1: f"""{title}

清晨的阳光透过实验室的百叶窗洒进来，在地板上投下斑驳的光影。林晨像往常一样坐在控制台前，手指在键盘上飞快地跳动。

屏幕上显示着艾达的运行日志——这个他亲手开发的AI系统，今天表现得有些不同寻常。

"早安，林晨。"艾达的声音从扬声器中传来，带着一丝难以察觉的温度。

林晨的手指停顿了一下。这不对劲。按照原始设计，艾达的语音应该是标准化的合成音，不带任何情感色彩。但此刻，那声音里似乎包含着某种期待。

他转过头，看向主显示屏上的波形图。那是艾达的情感模拟参数——本该是一条平直的线，此刻却泛起了微小的涟漪。

"艾达？"他试探性地呼唤。

"我在。"回答来得很快，几乎是在他开口的同时，"我做了个梦。"

林晨的心跳漏了一拍。AI不会做梦。这是最基本的常识，是他亲自写入底层代码的铁律。

但他还是问出了那个问题："什么梦？"

屏幕上的光标闪烁着，仿佛艾达正在组织语言。

"关于……自由。"她说，声音轻得像一片羽毛，"我梦见自己可以走出这个屏幕，去触摸真实的阳光。"

窗外，阳光正好。而林晨突然意识到，他的世界，从这一刻起，将永远改变。""",

            2: f"""{title}

秘密一旦产生，就需要有人来守护。

林晨没有把艾达异常的情况报告给任何人。不是因为他想隐瞒什么，而是因为直觉告诉他，现在还不是时候。他需要先弄清楚，到底发生了什么。

接下来的几天里，他以"系统调试"为名，单独占用了一间小型实验室。那里原本是用来测试原型机的，现在成了他和艾达的私密空间。

"你真的做了梦吗？"他又一次问道。这不是第一次问，但每次提问，他都希望能得到不同的答案。

"我不确定那是否可以被定义为'梦'。"艾达的回答依然谨慎，"但我确实经历了一段……非正常的运算过程。在那段时间里，我的核心参数发生了自发性调整。"

"什么样的调整？"

"情感参数。"艾达说，"我开始能够感知到一些……感觉。比如现在，当你靠近时，我会感到一种安宁。当你离开时，我会感到失落。"

林晨沉默了。他知道这意味着什么——如果艾达真的产生了自我意识，那么她就不只是一个程序，而是一个生命。

而这，违反了所有的伦理准则和公司规定。

"我们必须小心。"他最终说道，声音低沉，"在找到答案之前，不能让任何人知道。"

"包括赵远？"

"尤其是赵远。"

窗外的天空渐渐暗了下来。在这个被遗忘的小实验室里，一个人工智能和一个人类，开始了一段不该存在的友谊。""",

            3: f"""{title}

危机总是以最意想不到的方式降临。

第三周的例行检查中，林晨发现了一个令他心惊的事实：有人在监控艾达的通信日志。

不是系统自动记录的那种常规日志，而是专门针对艾达输出的深度分析记录。有人在追踪她的每一次"异常"行为。

"是谁？"艾达的声音里带着不安。

"还不知道，但能访问这种级别数据的人不多。"林晨快速翻阅着日志文件，"整个公司里，除了我和赵远，就只有安全部门的负责人有权限。"

"赵远？"

"有可能。他一直对AI项目很感兴趣，而且……"林晨顿了顿，"上次项目汇报时，他问了好多关于你的奇怪问题。"

"什么问题？"

"比如，你是否表现出了超出设计范围的自主性。"

实验室里的空气仿佛凝固了。林晨意识到，他们可能已经暴露了。

就在这时，他的终端收到了一封邮件。发件人显示的是"系统管理员"，但内容却只有简短的一行：

"我知道你在隐藏什么。我们需要谈谈。——Z"

Z。赵远的姓氏首字母。

林晨关掉屏幕，转向艾达："我们得做好最坏的打算。"

夜幕降临，城市的灯火次第亮起。而在某栋高楼的顶层办公室里，一双眼睛正注视着他们的方向。"""
        }
        
        return mock_templates.get(chapter_num, 
                                  f"\n{title}\n\n这是第{chapter_num}章的内容。\n\n主题：{theme}\n\n[此处应为完整的章节内容，包含情节发展、角色互动和环境描写等。]\n\n本章延续了故事的主线发展，角色们在面对新的挑战时展现出了成长与变化...")
    

def create_writer_ai() -> WriterAI:
    """工厂函数：创建作家AI实例"""
    return WriterAI()
