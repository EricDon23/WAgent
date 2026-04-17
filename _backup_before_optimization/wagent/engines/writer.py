#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
作家AI引擎 - 内容创作

功能：
1. 异步调用DeepSeek
2. 流式输出章节内容
3. 约束校验
4. 智能修改
"""

import json
import os
from typing import Dict, Any, Optional

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

from ..config import AsyncConfig, ConstraintConfig, SystemState
from ..display import RealtimeDisplay
from ..logger import ThinkingLogger
from ..cache import AsyncCacheManager


class WriterAI:
    """作家AI - 内容创作"""
    
    def __init__(self, config: AsyncConfig, logger: ThinkingLogger,
                 cache: AsyncCacheManager):
        self.cfg = config
        self.logger = logger
        self.cache = cache
        self.constraints = ConstraintConfig()
        
        self.api_key = os.getenv('DEEPSEEK_API_KEY', '')
        self.base_url = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
        self.model = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
    
    async def generate(self, ch_num: int, setting: Dict,
                      kb: Optional[Dict] = None, prev_chapter: str = "",
                      instructions: str = "", display: RealtimeDisplay = None) -> Dict:
        """生成章节"""
        start_time = __import__('time').time()
        ck = self.cache.key('writer',ch_num,setting.get('story_name',''),instructions[:50])
        
        cached = await self.cache.get(ck)
        if cached:
            return cached
        
        display.update(SystemState.WRITER_GENERATING,f"创作第{ch_num}章...",5)
        
        system = self._build_prompt(setting,kb)
        user = f"请生成第{ch_num}章。\n"
        if prev_chapter:
            user += f"\n前一章结尾:\n{prev_chapter[-600:]}\n"
        if instructions:
            user += f"\n特殊要求: {instructions}\n"
        
        constraints = setting.get('constraints','温暖基调,第三人称,1500-2500字/章')
        user += f"\n**约束**: {constraints}\n**字数**: {self.constraints.min_words}-{self.constraints.max_words}字\n"
        
        messages = [{"role":"system","content":system},{"role":"user","content":user}]
        
        result_data = {"success":False,"data":None,"error":None,"metadata":{}}
        full_content = ""
        
        try:
            from rich.live import Live
            from rich.panel import Panel
            from rich.markdown import Markdown
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization":f"Bearer {self.api_key}","Content-Type":"application/json"},
                    json={"model":self.model,"messages":messages,"temperature":1.0,
                           "max_tokens":self.cfg.writer_max_tokens,"stream":True},
                    timeout=aiohttp.ClientTimeout(total=self.cfg.stream_timeout)
                ) as resp:
                    
                    if resp.status != 200:
                        raise Exception(f"API错误 {resp.status}")
                    
                    with Live(console=display.console if display else None,
                             refresh_per_second=10) as live:
                        live.update(Panel("[italic]等待开始...[/italic]",
                                        title=f"✍️ 第{ch_num}章",border_style="magenta"))
                        
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
                                            full_content += c
                                            wc = len(full_content)
                                            preview = full_content[-400:] if wc>400 else full_content
                                            live.update(Panel(Markdown(preview),
                                                            title=f"✍️ 第{ch_num}章 ({wc}字)",
                                                            border_style="magenta"))
                                            display.update(SystemState.WRITER_GENERATING,
                                                         f"创作中...({wc}字)",min(95,5+wc/50))
                                    except:
                                        continue
                        
                        live.update(Panel(
                            Markdown(full_content[-500:] if len(full_content)>500 else full_content),
                            title=f"✅ 第{ch_num}章完成 ({len(full_content)}字)",
                            border_style="green"))
            
            wc = len(full_content)
            valid,msg = self.constraints.validate(wc)
            
            result_data["success"] = True
            result_data["data"] = {
                "content":full_content,"word_count":wc,"chapter_num":ch_num,
                "constraint_check":{"passed":valid,"message":msg}
            }
            result_data["metadata"] = {"model":self.model,"time":__import__('time').time()-start_time,"words":wc}
        
        except Exception as e:
            print(f"[red]❌ 作家AI错误: {e}[/red]")
            mock = f"# 第{ch_num}章\n\nMock模式内容。"
            result_data["success"] = True
            result_data["data"] = {"content":mock,"word_count":len(mock),"chapter_num":ch_num,
                                   "constraint_check":{"passed":True,"message":"Mock"}}
            result_data["metadata"] = {"model":"mock","time":0.1}
        
        await self.logger.log('writer','complete',f'第{ch_num}章 {result_data["data"]["word_count"]}字', result_data["metadata"])
        await self.cache.set(ck,result_data)
        display.update(SystemState.WRITER_GENERATING,"完成!",100)
        return result_data
    
    async def modify(self, original: Dict, request: str, display: RealtimeDisplay) -> Dict:
        """智能修改章节"""
        display.update(SystemState.MODIFYING,"修改章节中...",40)
        
        content = original['data']['content']
        ch_num = original['data']['chapter_num']
        
        prompt = f"""你是专业编辑，根据要求修改章节。

原内容:
{content}

修改要求: {request}

原则: 只改相关部分，保持连贯。输出完整修改后内容。"""

        messages = [
            {"role":"system","content":"你是专业编辑，精准修改内容。"},
            {"role":"user","content":prompt}
        ]
        
        new_content = content
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization":f"Bearer {self.api_key}","Content-Type":"application/json"},
                    json={"model":self.model,"messages":messages,"temperature":0.8,
                           "max_tokens":4096,"stream":False},
                    timeout=aiohttp.ClientTimeout(total=180)
                ) as resp:
                    if resp.status == 200:
                        d = await resp.json()
                        new_content = d['choices'][0]['message']['content']
        except Exception as e:
            print(f"[yellow]⚠️ 修改失败: {e}[/yellow]")
        
        wc = len(new_content)
        valid,msg = self.constraints.validate(wc)
        
        modified = {"success":True,"data":{
            "content":new_content,"word_count":wc,"chapter_num":ch_num,
            "constraint_check":{"passed":valid,"message":msg},"modified":True,
            "modification_request":request
        },"metadata":{"model":self.model,"modified":True}}
        
        await self.logger.log('writer','modify',request[:100])
        display.update(SystemState.MODIFYING,"完成!",100)
        return modified
    
    def _build_prompt(self,setting:Dict,kb:Optional[Dict]) -> str:
        p = f"""你是专业小说作家。

**故事**: {setting.get('story_name','')}
**梗概**: {setting.get('story_summary','')}

**角色**:
"""
        for ch in setting.get('characters',[]):
            p += f"- {ch.get('name','')}({ch.get('role','')}): {ch.get('personality','')}\n"
        
        if kb and kb.get('summary'):
            p += f"\n**参考资料**:\n{kb['summary']}\n"
        
        c = setting.get('constraints','温暖基调,第三人称叙事')
        p += f"\n**约束**: {c}\n**要求**: 情节推进自然，细节丰富"
        return p