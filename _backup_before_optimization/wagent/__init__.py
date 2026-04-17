"""
WAgent v4.2 - 模块化故事创作系统

架构设计：
- 高内聚低耦合原则
- 独立功能模块
- 清晰的依赖关系

模块结构：
├── config.py        # 核心配置与数据结构
├── normalizer.py    # 文本规范化工具
├── display.py       # 实时状态显示系统
├── logger.py        # 日志记录器
├── cache.py         # 缓存管理器
├── engines/         # AI引擎模块
│   ├── director.py  # 导演AI
│   ├── researcher.py# 研究员AI
│   └── writer.py    # 作家AI
├── utils/           # 工具模块
│   ├── archiver.py  # ZIP归档工具
│   └── interactive.py # 交互式判断工具
└── controller.py    # 主控制器

作者: WAgent Team
版本: v4.2 Modular
日期: 2026-04-17
"""

__version__ = "4.2 Modular"
__author__ = "WAgent Team"