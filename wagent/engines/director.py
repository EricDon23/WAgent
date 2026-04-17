#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
导演AI引擎 - 故事蓝图制定者

功能：
1. 异步调用豆包模型
2. 流式输出
3. 结构化故事设定生成
4. 设定细化/修改
5. Mock数据fallback
"""

import json
import os
import re
import asyncio
from typing import Dict, Any, Optional

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    aiohttp = None
    AIOHTTP_AVAILABLE = False

from ..config import AsyncConfig, FeatureFlags, SystemState
from ..display import RealtimeDisplay
from ..logger import ThinkingLogger
from ..cache import AsyncCacheManager


class DirectorAI:
    """
    导演AI - 故事蓝图制定者
    
    职责：
    - 将用户创意转化为结构化故事设定
    - 生成完整的StorySetting JSON
    - 支持设定修改和细化
    
    使用模型：豆包 (Doubao) - 温度0（确保稳定性）
    """
    
    def __init__(self, config: AsyncConfig, logger: ThinkingLogger, 
                 cache: AsyncCacheManager):
        self.cfg = config
        self.logger = logger
        self.cache = cache
        
        self.api_key = os.getenv('DOUBAO_API_KEY', '')
        self.base_url = os.getenv('DOUBAO_BASE_URL', 
                               'https://ark.cn-beijing.volces.com/api/v3')
        self.model = os.getenv('DOUBAO_MODEL', 'doubao-seed-2-0-pro-260215')
        
        if not AIOHTTP_AVAILABLE:
            raise ImportError("需要安装aiohttp: pip install aiohttp")
    
    async def generate(self, user_input: str, display: RealtimeDisplay) -> Dict:
        """生成故事设定（带流式输出）"""
        start_time = __import__('time').time()
        ck = self.cache.key('director', user_input)
        
        # 检查缓存
        cached = await self.cache.get(ck)
        if cached:
            await self.logger.log('director', 'cache_hit', cached.get('story_name', ''))
            return cached
        
        await self.logger.log('director', 'start', user_input[:50])
        display.update(SystemState.DIRECTOR_GENERATING, "导演AI构思中...", 10)
        
        system_prompt = f"""你是专业的故事导演，将用户的简单提示转化为完整的结构化故事设定。

当前日期：{__import__('datetime').datetime.now().strftime('%Y-%m-%d')}

严格要求：
1. 输出必须为完整JSON格式
2. 所有字段不得留空
3. 自动补全缺失信息
4. research_needs包含3-5个具体主题

JSON格式：
{{
    "story_name": "名称",
    "story_summary": "一句话梗概",
    "story_intro": "200字简介",
    "theme": "主题",
    "characters": [{{"name":"名","role":"身份","personality":"性格","background":"背景"}}],
    "relationships": "关系描述",
    "plot_outline": "三幕大纲",
    "constraints": "约束(风格/视角/字数)",
    "research_needs": ["主题1","主题2"]
}}"""

        messages = [
            {"role":"system","content":system_prompt},
            {"role":"user","content":f"用户输入: {user_input}"}
        ]
        
        result = None
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": 0.0,
                        "max_tokens": self.cfg.director_max_tokens,
                        "stream": True
                    },
                    timeout=aiohttp.ClientTimeout(total=self.cfg.stream_timeout)
                ) as resp:
                    
                    if resp.status != 200:
                        raise Exception(f"API错误 {resp.status}")
                    
                    full = ""
                    async for line in resp.content:
                        if line:
                            t = line.decode('utf-8').strip()
                            if t.startswith('data: '):
                                d = t[6:]
                                if d == '[DONE]':
                                    break
                                try:
                                    data = json.loads(d)
                                    delta = data.get('choices',[{}])[0].get('delta',{})
                                    c = delta.get('content','')
                                    if c:
                                        full += c
                                        p = min(90, 10+len(full)/50)
                                        display.update(SystemState.DIRECTOR_GENERATING,
                                                     f"生成中...({len(full)}字符)", p)
                                except:
                                    continue
                    
                    if full.strip().startswith('{'):
                        result = json.loads(full)
                    else:
                        m = re.search(r'\{.*\}',full,re.DOTALL)
                        result = json.loads(m.group()) if m else {}
        
        except Exception as e:
            print(f"[red]❌ 导演AI错误: {e}[/red]")
            await self.logger.log('director','error',str(e))
            
            # Mock数据fallback
            result = {
                "story_name":f"《{user_input[:20]}》",
                "story_summary":f"关于{user_input}的故事",
                "story_intro":f"这是一个以{user_input}为核心的故事...",
                "theme":"探索与成长",
                "characters":[{"name":"主角","role":"核心人物","personality":"勇敢","background":"普通"}],
                "relationships":"主要角色间的关系",
                "plot_outline":"起因→发展→结局",
                "constraints":"温暖基调，第三人称，1500-2500字/章",
                "research_needs":[user_input,"相关背景","同类作品"]
            }
        
        elapsed = __import__('time').time() - start_time
        await self.logger.log('director','complete',result.get('story_name',''),{'time':elapsed})
        await self.cache.set(ck,result)
        display.update(SystemState.DIRECTOR_GENERATING,"完成!",100,f"设定: {result.get('story_name','')}")
        
        return result
    
    async def refine(self, current: Dict, request: str, display: RealtimeDisplay) -> Dict:
        """细化/修改故事设定"""
        display.update(SystemState.MODIFYING,"修改设定中...",30)
        
        prompt = f"""根据用户意见调整故事设定。

当前设定：
```json
{json.dumps(current, ensure_ascii=False, indent=2)}
```

修改要求：{request}

原则：只改要求的部分，保持其他不变。输出完整JSON。"""

        messages = [
            {"role":"system","content":"你是专业导演，擅长根据反馈优化设定。"},
            {"role":"user","content":prompt}
        ]
        
        result = current.copy()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization":f"Bearer {self.api_key}","Content-Type":"application/json"},
                    json={"model":self.model,"messages":messages,"temperature":0.0,
                           "max_tokens":2048,"stream":False},
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as resp:
                    if resp.status == 200:
                        d = await resp.json()
                        c = d['choices'][0]['message']['content']
                        if c.strip().startswith('{'):
                            result = json.loads(c)
        except Exception as e:
            print(f"[yellow]⚠️ 修改失败: {e}[/yellow]")
        
        await self.logger.log('director','refine',request[:100])
        display.update(SystemState.MODIFYING,"完成!",100)
        return result