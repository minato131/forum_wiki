#!/usr/bin/env python
import os
import sys
import logging

# Настройка пути - исправляем путь к проекту
project_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_path)

print(f"📁 Запуск синхронного бота из: {project_path}")

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'witcher_wiki.settings')

try:
    import django
    django.setup()
    print("✅ Django настроен успешно")
except Exception as e:
    print(f"❌ Ошибка настройки Django: {e}")
    sys.exit(1)

# Импортируем бота
try:
    from wiki.telegram_bot_sync import sync_bot
    print("✅ Синхронный бот импортирован успешно")
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    # Покажем подробную информацию об ошибке
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

if __name__ == '__main__':
    print("🚀 Запуск бота...")
    sync_bot.run()