#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WAgent V3.1 AI模块包

统一导出接口：
- 导演AI (director.py)
- 研究AI (researcher.py)
- 作家AI (writer.py)
- 设定校验器 (self_checker.py)

V3.1特性：
- 分层存储支持
- 双向同步集成
- 10阶段进度显示
- rich库界面美化
"""

from ai.director import DirectorAI, create_director_ai
from ai.researcher import ResearcherAI, create_researcher_ai
from ai.writer import WriterAI, create_writer_ai
from ai.self_checker import SettingConsistencyChecker, create_checker

__all__ = [
    # AI核心模块
    'DirectorAI',
    'create_director_ai',
    'ResearcherAI', 
    'create_researcher_ai',
    'WriterAI',
    'create_writer_ai',
    
    # 质量保障工具
    'SettingConsistencyChecker',
    'create_checker',
]

__version__ = "V3.1"
__author__ = "WAgent Team"
