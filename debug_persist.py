import sys, tempfile, shutil
sys.path.insert(0, '.')
from pathlib import Path

test_dir = tempfile.mkdtemp()
print(f"测试目录: {test_dir}")

from wagent.stories_manager import SessionAgentManager

manager = SessionAgentManager(base_dir=test_dir)
manager.create_session("persist_001", "story_a")
manager.start_agent("persist_001", "stories/story_a")
manager.update_instance_stats("persist_001", words_generated=500)

sessions_file = Path(test_dir) / "_sessions_registry.json"
print(f"注册表文件存在: {sessions_file.exists()}")
print(f"目录内容: {list(Path(test_dir).iterdir()) if Path(test_dir).exists() else '目录不存在'}")

if sessions_file.exists():
    import json
    with open(sessions_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"数据: {list(data.keys())}")
else:
    print("文件不存在！检查instances:")
    print(f"  instances数量: {len(manager.instances)}")
    for sid, inst in manager.instances.items():
        print(f"  - {sid}: state={inst.state.value}")

shutil.rmtree(test_dir)
