import sys, tempfile, os
sys.path.insert(0, '.')
from wagent.core_upgrade_v6 import *
from pathlib import Path

# 调试1: get_session_by_storytree
test_dir = tempfile.mkdtemp()
binder = StorySessionBinder(base_dir=test_dir)
binder.bind('sess_005', 'stories/reverse_lookup')

result = binder.get_session_by_storytree('stories/reverse_lookup')
print(f'1. get_session_by_storytree: {result}')

binding = binder.get_binding('sess_005')
if binding:
    print(f'   绑定session_id: {binding.session_id}')
    print(f'   绑定storytree_path: {binding.storytree_path}')
    print(f'   路径解析后: {Path(binding.storytree_path).resolve()}')

# 测试路径比较
input_path = Path('stories/reverse_lookup').resolve()
stored_path = Path(binding.storytree_path).resolve()
print(f'   输入路径解析: {input_path}')
print(f'   是否相等: {input_path == stored_path}')

# 调试2&3: KnowledgeBaseManager
test_dir2 = tempfile.mkdtemp()
kb = KnowledgeBaseManager(base_path=os.path.join(test_dir2, 'knowledge'))

entry = kb.add_entry('量子计算基础', '量子比特、叠加态等概念介绍', 'science_fiction', ['量子', '物理'])
print(f'\n2. add_entry category: {entry.category}')
print(f'   期望: {KnowledgeCategory.SCIENCE_FICTION}')
print(f'   是否相等: {entry.category == KnowledgeCategory.SCIENCE_FICTION}')

kb.add_entry('科幻知识1', '太空探索', 'sci_fi', ['科幻'])
kb.add_entry('科幻知识2', '时间旅行', 'sci_fi', ['时间'])

results = kb.search_knowledge('', category_filter=KnowledgeCategory.SCIENCE_FICTION)
print(f'\n3. SCI_FI过滤结果数: {len(results)} (期望>=2)')
for r in results:
    print(f'   - {r.title} category={r.category}')

# 查看所有条目
print(f'\n所有条目:')
for eid, e in kb.entries.items():
    print(f'   - {e.title}: {e.category}')
