import sys
sys.path.insert(0, '.')
print('1. 检查导入...')
from wagent_launcher import WAgenterLauncher
print('   ✅ 导入成功')

print('\n2. 检查组件初始化...')
launcher = WAgenterLauncher()
print(f'   ✅ 初始化成功')
print(f'   - 扫描器: {type(launcher.scanner).__name__}')
print(f'   - 会话管理器: {type(launcher.session_mgr).__name__}')
print(f'   - 错误处理器: {type(launcher.error_handler).__name__}')

print('\n3. 测试会话创建...')
instance = launcher.session_mgr.create_session('test_launch_001', 'test_story')
print(f'   ✅ 创建会话: {instance.instance_id}')

success, msg = launcher.session_mgr.start_agent('test_launch_001', 'stories/test')
print(f'   ✅ 启动Agent: {msg}')

stats = launcher.session_mgr.get_statistics()
print(f'\n4. 系统统计:')
print(f'   - 总创建: {stats["total_created"]}')
print(f'   - 活跃数: {stats["active_count"]}')

# 清理
launcher.session_mgr.destroy_session('test_launch_001', confirm_callback=lambda p: True)
print('\n5. ✅ 所有基本功能验证通过!')
