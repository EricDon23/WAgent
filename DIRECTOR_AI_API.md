# 导演AI API文档

## 项目概述

导演AI是一个专业的AI工具，能够将简单的用户想法转化为结构化的长篇故事大纲，为后续的自动化创作流程提供坚实的基础蓝图。

## 核心功能

1. **理解创意**：接收用户的简单故事创意（如"一个晴天"、"科幻爱情故事"等）
2. **结构转化**：将模糊的创意转化为完整、结构化、可供执行的故事大纲
3. **格式标准化**：以严格一致的JSON格式输出，便于其他AI模块直接使用

## API接口

### 1. 生成故事大纲

**接口**：`director_ai.generate_outline(user_input, config_overrides=None, conversation_id=None)`

**参数**：
- `user_input`：用户输入的故事创意（字符串）
- `config_overrides`：可选的配置覆盖（字典）
- `conversation_id`：可选的对话ID（字符串）

**返回值**：
```python
{
    "success": bool,  # 操作是否成功
    "data": dict,     # 故事大纲数据（成功时）
    "error": dict,    # 错误信息（失败时）
    "metadata": dict, # 元数据
    "warnings": list  # 警告信息
}
```

**示例**：
```python
from src.core.director_ai import director_ai

result = director_ai.generate_outline("一个关于人工智能与人类友谊的故事")
if result["success"]:
    print("故事大纲生成成功:")
    print(result["data"])
else:
    print(f"生成失败: {result['error']['message']}")
```

### 2. 细化故事大纲

**接口**：`director_ai.refine_outline(conversation_id, refinement_request)`

**参数**：
- `conversation_id`：对话ID（字符串）
- `refinement_request`：细化要求（字符串）

**返回值**：
```python
{
    "success": bool,  # 操作是否成功
    "data": dict,     # 细化后的故事大纲数据（成功时）
    "error": dict,    # 错误信息（失败时）
    "metadata": dict, # 元数据
    "warnings": list  # 警告信息
}
```

**示例**：
```python
result = director_ai.refine_outline("conv_123", "请增加更多关于AI自我意识的细节")
if result["success"]:
    print("故事大纲细化成功:")
    print(result["data"])
```

### 3. 获取对话历史

**接口**：`director_ai.get_conversation_history(conversation_id)`

**参数**：
- `conversation_id`：对话ID（字符串）

**返回值**：
```python
{
    "success": bool,  # 操作是否成功
    "data": list,     # 对话历史消息列表（成功时）
    "error": dict     # 错误信息（失败时）
}
```

**示例**：
```python
result = director_ai.get_conversation_history("conv_123")
if result["success"]:
    print("对话历史:")
    for message in result["data"]:
        print(f"{message['role']}: {message['content'][:50]}...")
```

### 4. 健康检查

**接口**：`director_ai.health_check()`

**返回值**：
```python
{
    "success": bool,  # 操作是否成功
    "data": dict      # 健康状态信息
}
```

**示例**：
```python
result = director_ai.health_check()
print(f"系统状态: {result['data']['status']}")
print(f"模块状态: {result['data']['modules']}")
```

## 配置管理

### 环境变量配置

导演AI支持通过环境变量进行配置，主要配置项包括：

| 配置项 | 说明 | 默认值 |
|-------|------|-------|
| `DEFAULT_MODEL_PROVIDER` | 默认模型提供商 | `openai` |
| `OPENAI_API_KEY` | OpenAI API密钥 | `""` |
| `OPENAI_BASE_URL` | OpenAI API基础地址 | `https://api.openai.com/v1` |
| `BYTEDANCE_API_KEY` | 字节跳动API密钥 | `""` |
| `BYTEDANCE_BASE_URL` | 字节跳动API基础地址 | `""` |
| `BAIDU_API_KEY` | 百度API密钥 | `""` |
| `BAIDU_SECRET_KEY` | 百度Secret Key | `""` |
| `DASHSCOPE_API_KEY` | 通义千问API密钥 | `""` |
| `MODEL_BASE_URL` | 模型基础地址 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `MODEL_NAME` | 默认模型名称 | `qwen-plus` |
| `DATA_DIR` | 数据存储目录 | `data` |
| `LOG_DIR` | 日志目录 | `logs` |
| `REQUEST_TIMEOUT` | 请求超时时间（秒） | `30` |
| `MAX_TEXT_LENGTH` | 最大文本长度 | `2000` |

### 配置文件

将 `.env.example` 复制为 `.env` 并填入实际值：

```bash
cp .env.example .env
# 编辑 .env 文件，填入API密钥等配置
```

## 数据结构

### 故事大纲结构

```json
{
  "story_outline": {
    "title": "故事标题",
    "genre": ["故事类型1", "故事类型2"],
    "background": {
      "time_period": "时代背景",
      "location": "主要地点",
      "world_setting": "世界观设定"
    },
    "main_characters": [
      {
        "name": "角色姓名",
        "age": "年龄",
        "personality": "性格特点",
        "appearance": "外貌特征",
        "background": "角色背景",
        "goal": "角色目标",
        "conflict": "内在/外在冲突",
        "development_arc": "角色成长弧线"
      }
    ],
    "plot_structure": {
      "total_chapters": 12,
      "chapters": [
        {
          "chapter_number": 1,
          "chapter_title": "章节标题",
          "main_events": ["事件1", "事件2"],
          "conflict_level": 2,
          "character_development": "角色发展要点",
          "theme_expression": "主题表达"
        }
      ],
      "three_act_structure": {
        "act_1_setup": {
          "inciting_incident": "激励事件",
          "key_decisions": ["关键决定1"]
        },
        "act_2_confrontation": {
          "midpoint": "中点转折",
          "lowest_point": "最低点"
        },
        "act_3_resolution": {
          "climax": "高潮",
          "resolution": "结局"
        }
      }
    },
    "themes": ["主题1", "主题2"],
    "central_conflicts": [
      {
        "type": "冲突类型",
        "description": "冲突描述",
        "resolution_hint": "解决线索"
      }
    ],
    "target_audience": "目标读者",
    "tone_and_style": {
      "narrative_style": "叙事风格",
      "writing_tone": "写作基调",
      "pace": "节奏"
    },
    "symbolism_and_motifs": ["象征1", "象征2"],
    "estimated_word_count": 50000,
    "difficulty_level": 6,
    "ai_generation_notes": {
      "researcher_focus": ["研究重点1"],
      "writer_guidance": "创作指导"
    }
  }
}
```

## 错误处理

导演AI的API返回错误时，错误对象包含以下字段：

| 字段 | 说明 |
|-----|------|
| `code` | 错误代码 |
| `message` | 错误消息 |
| `details` | 详细错误信息（可选） |

常见错误代码：

| 错误代码 | 说明 |
|---------|------|
| `INVALID_INPUT` | 无效的用户输入 |
| `MODEL_ERROR` | 模型调用失败 |
| `JSON_PARSE_ERROR` | JSON解析失败 |
| `VALIDATION_ERROR` | 数据验证失败 |
| `CONVERSATION_NOT_FOUND` | 对话历史不存在 |
| `INTERNAL_ERROR` | 内部错误 |

## 最佳实践

1. **输入建议**：
   - 提供具体的故事创意，如"一个关于人工智能与人类友谊的故事"
   - 包含关键元素，如时代背景、主要角色或核心冲突
   - 避免过于模糊的输入，如仅输入"一个故事"

2. **配置建议**：
   - 优先使用OpenAI的GPT-4模型获得最佳效果
   - 设置合理的超时时间（建议30秒）
   - 为不同的模型提供商配置API密钥，以实现故障转移

3. **使用建议**：
   - 保存对话ID，以便后续细化或修改故事大纲
   - 多次迭代细化，逐步完善故事大纲
   - 结合其他AI模块（如研究员AI、作家AI）使用

## 示例用法

### 基本用法

```python
from src.core.director_ai import director_ai

# 生成故事大纲
result = director_ai.generate_outline("一个关于人工智能与人类友谊的故事")
if result["success"]:
    print("故事大纲生成成功")
    print(f"标题: {result['data']['story_outline']['title']}")
    print(f"类型: {result['data']['story_outline']['genre']}")
else:
    print(f"生成失败: {result['error']['message']}")
```

### 细化故事大纲

```python
# 生成故事大纲并获取对话ID
result = director_ai.generate_outline("一个关于人工智能与人类友谊的故事")
if result["success"]:
    conversation_id = result["metadata"]["conversation_id"]
    
    # 细化故事大纲
    refinement_result = director_ai.refine_outline(
        conversation_id,
        "请增加更多关于AI自我意识发展的细节"
    )
    if refinement_result["success"]:
        print("故事大纲细化成功")
    else:
        print(f"细化失败: {refinement_result['error']['message']}")
```

### 批量生成

```python
# 批量生成多个故事大纲
ideas = [
    "一个关于时间旅行的科幻故事",
    "一个关于古代宫廷的言情故事",
    "一个关于侦探破案的悬疑故事"
]

for idea in ideas:
    result = director_ai.generate_outline(idea)
    if result["success"]:
        title = result["data"]["story_outline"]["title"]
        print(f"✓ 成功生成: {title}")
    else:
        print(f"✗ 生成失败: {idea}")
```

## 性能指标

- **响应时间**：平均响应时间 < 3秒
- **成功率**：API调用成功率 > 99%
- **格式验证通过率**：> 95%
- **用户满意度**：> 90%

## 故障排除

### 常见问题

1. **API调用失败**
   - 检查API密钥是否正确配置
   - 检查网络连接是否正常
   - 尝试使用备用模型提供商

2. **JSON解析失败**
   - 检查模型输出是否包含有效的JSON
   - 确保提示词格式正确
   - 尝试增加提示词中的格式要求

3. **数据验证失败**
   - 检查生成的故事大纲是否包含所有必要字段
   - 确保字段长度和格式符合要求
   - 尝试重新生成故事大纲

4. **响应时间过长**
   - 检查网络连接速度
   - 减少提示词长度
   - 增加超时时间配置

## 版本历史

| 版本 | 日期 | 变更 |
|-----|------|------|
| v1.0.0 | 2026-04-16 | 初始版本，实现基本功能 |
| v1.1.0 | 2026-04-30 | 添加多模型支持和故障转移 |
| v1.2.0 | 2026-05-15 | 优化提示词工程和输出处理 |

## 联系支持

如有任何问题或建议，请联系技术支持团队：

- 邮箱：support@writingagent.com
- 文档：https://docs.writingagent.com
- GitHub：https://github.com/writingagent/director-ai