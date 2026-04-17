#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
研究员AI引擎 - 资料收集

功能：
1. 异步调用通义千问
2. 生成结构化知识库
3. 关键发现提取
"""

import json
import os
import re
from typing import Dict, Any, Optional

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

from ..config import AsyncConfig, SystemState
from ..display import RealtimeDisplay
from ..logger import ThinkingLogger
from ..cache import AsyncCacheManager


class ResearcherAI:
    """研究员AI - 资料收集"""
    
    def __init__(self, config: AsyncConfig, logger: ThinkingLogger, 
                 cache: AsyncCacheManager):
        self.cfg = config
        self.logger = logger
        self.cache = cache
        
        self.api_key = os.getenv('DASHSCOPE_API_KEY', '')
        self.base_url = os.getenv('DASHSCOPE_BASE_URL',
                               'https://dashscope.aliyuncs.com/compatible-mode/v1')
        self.model = os.getenv('DASHSCOPE_MODEL', 'qwen-plus')
        
        if not AIOHTTP_AVAILABLE:
            raise ImportError("需要安装aiohttp")
    
    async def generate(self, needs: list, title: str, genre: str,
                       display: RealtimeDisplay) -> Dict:
        """生成知识库"""
        start_time = __import__('time').time()
        ck = self.cache.key(f"researcher:{','.join(needs)}:{title}")
        
        cached = await self.cache.get(ck)
        if cached:
            return cached
        
        display.update(SystemState.RESEARCHER_GENERATING,"研究员检索中...",10,f"收集{len(needs)}个主题...")
        
        prompt = f"""你是专业的研究员，为故事创作收集背景资料。

故事: {title}
类型: {genre}

研究需求:
{chr(10).join(f'- {n}' for n in needs)}

请生成知识库(JSON):
{{"research_topic":"主题","summary":"200字摘要","key_findings":[{{"category":"分类","finding":"发现"}}],"references":[]}}"""

        messages = [
            {"role":"system","content":"你是严谨的研究员，提供准确资料。"},
            {"role":"user","content":prompt}
        ]
        
        result = None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization":f"Bearer {self.api_key}","Content-Type":"application/json"},
                    json={"model":self.model,"messages":messages,"temperature":0.0,
                           "max_tokens":self.cfg.researcher_max_tokens,"stream":True},
                    timeout=aiohttp.ClientTimeout(total=self.cfg.stream_timeout)
                ) as resp:
                    if resp.status == 200:
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
                                            p = min(95,10+len(full)/80)
                                            display.update(SystemState.RESEARCHER_GENERATING,
                                                         f"检索中...({len(full)}字符)",p)
                                    except:
                                        continue
                        
                        if full.strip().startswith('{'):
                            result = json.loads(full)
                        else:
                            m = re.search(r'\{.*\}',full,re.DOTALL)
                            result = json.loads(m.group()) if m else {}
        except Exception as e:
            print(f"[yellow]⚠️ 研究员错误: {e}[/yellow]")
            result = {"research_topic":f"{title}研究","summary":"基础研究资料",
                      "key_findings":[{"category":"通用","finding":n} for n in needs],"references":[]}
        
        if not result:
            result = {"research_topic":f"{title}研究","summary":"","key_findings":[],"references":[]}
        
        await self.logger.log('researcher','complete',result.get('summary','')[:50],
                             {'time':__import__('time').time()-start_time})
        await self.cache.set(ck,result)
        display.update(SystemState.RESEARCHER_GENERATING,"完成!",100,f"{len(result.get('key_findings',[]))}条发现")
        return result