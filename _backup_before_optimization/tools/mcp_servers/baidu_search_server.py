"""
MCP百度搜索服务
基于FastMCP构建的MCP工具服务
使用Selenium进行无头浏览器自动化搜索

技术实现：MCP 1.20.0 + FastMCP + Selenium 4.15.2
"""

import json
import re
from typing import List, Dict, Optional
from mcp.server.fastmcp import FastMCP


class BaiduSearchServer:
    """百度搜索MCP服务器"""
    
    def __init__(self):
        """初始化搜索服务器"""
        self.mcp = FastMCP("baidu-search-server")
        self._register_tools()
        
        print("🔧 MCP百度搜索服务初始化完成")
    
    def _register_tools(self):
        """注册MCP工具"""
        
        @self.mcp.tool()
        async def search_baidu(
            query: str,
            num_results: int = 5,
            language: str = "zh-cn"
        ) -> str:
            """
            使用百度搜索引擎检索信息
            
            Args:
                query: 搜索关键词
                num_results: 返回结果数量（1-10）
                language: 语言设置
                
            Returns:
                JSON格式的搜索结果字符串
            """
            try:
                results = self._perform_search(query, num_results)
                
                return json.dumps({
                    "success": True,
                    "query": query,
                    "results_count": len(results),
                    "results": results
                }, ensure_ascii=False)
                
            except Exception as e:
                return json.dumps({
                    "success": False,
                    "error": str(e),
                    "results": []
                }, ensure_ascii=False)
        
        @self.mcp.tool()
        async def get_search_summary(query: str) -> str:
            """
            获取搜索结果的摘要信息
            
            Args:
                query: 搜索关键词
                
            Returns:
                摘要文本
            """
            try:
                results = self._perform_search(query, 3)
                
                if not results:
                    return f"未找到关于'{query}'的相关信息"
                
                summary_parts = [f"关于'{query}'的搜索摘要："]
                
                for i, result in enumerate(results[:3], 1):
                    summary_parts.append(f"\n{i}. {result['title']}")
                    summary_parts.append(f"   {result['snippet'][:150]}...")
                
                return "\n".join(summary_parts)
                
            except Exception as e:
                return f"获取摘要失败: {e}"
    
    def _perform_search(self, query: str, num_results: int) -> List[Dict[str, str]]:
        """
        执行搜索（使用模拟数据或实际Selenium）
        
        Args:
            query: 搜索词
            num_results: 结果数
            
        Returns:
            搜索结果列表
        """
        # 尝试使用Selenium进行真实搜索
        try:
            return self._selenium_search(query, num_results)
        except Exception as e:
            print(f"⚠️ Selenium搜索失败: {e}，使用模拟数据")
            return self._generate_mock_results(query, num_results)
    
    def _selenium_search(self, query: str, num_results: int) -> List[Dict[str, str]]:
        """使用Selenium进行真实搜索"""
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        import time
        
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        
        driver = webdriver.Chrome(options=options)
        
        try:
            url = f"https://www.baidu.com/s?wd={query}"
            driver.get(url)
            
            time.sleep(2)
            
            results = []
            elements = driver.find_elements(By.CSS_SELECTOR, '.result.c-container')
            
            for element in elements[:num_results]:
                try:
                    title_element = element.find_element(By.CSS_SELECTOR, 'h3 a')
                    snippet_element = element.find_element(By.CSS_SELECTOR, '.c-abstract')
                    
                    title = title_element.text.strip()
                    url_link = title_element.get_attribute('href') or ""
                    snippet = snippet_element.text.strip() if snippet_element else ""
                    
                    if title:
                        results.append({
                            "title": title,
                            "url": url_link,
                            "snippet": snippet
                        })
                        
                except Exception as e:
                    continue
            
            return results
            
        finally:
            driver.quit()
    
    def _generate_mock_results(self, query: str, num_results: int) -> List[Dict[str, str]]:
        """生成模拟搜索结果（备用方案）"""
        results = []
        
        mock_data = [
            {
                "title": f"{query} - 维基百科",
                "url": "https://zh.wikipedia.org",
                "snippet": f"关于{query}的详细百科介绍，包含历史背景、发展现状和相关知识。"
            },
            {
                "title": f"{query}研究综述 - 学术论文",
                "url": "#academic",
                "snippet": f"最新的{query}研究成果和学术观点，为创作提供专业参考。"
            },
            {
                "title": f"{query}在实际应用中的案例分析",
                "url": "#cases",
                "snippet": f"{query}在不同领域的应用实例和实践经验总结。"
            }
        ]
        
        for i in range(min(num_results, len(mock_data))):
            result = mock_data[i].copy()
            result["title"] = f"[模拟] {result['title']}"
            results.append(result)
        
        return results
    
    def run_server(self, host: str = "localhost", port: int = 8002):
        """
        启动MCP服务器
        
        Args:
            host: 主机地址
            port: 端口号
        """
        print(f"🚀 启动MCP百度搜索服务 | {host}:{port}")
        self.mcp.run(transport="stdio")


if __name__ == "__main__":
    server = BaiduSearchServer()
    server.run_server()
