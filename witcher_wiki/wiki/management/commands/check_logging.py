from django.core.management.base import BaseCommand
from wiki.models import ActionLog
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Проверка работы системы логирования'

    def handle(self, *args, **options):
        # Проверяем количество записей в логах
        log_count = ActionLog.objects.count()
        self.stdout.write(f"📊 Всего записей в логах: {log_count}")

        # Показываем последние записи
        recent_logs = ActionLog.objects.all().order_by('-created_at')[:5]
        if recent_logs:
            self.stdout.write("📝 Последние записи:")
            for log in recent_logs:
                self.stdout.write(f"   {log.created_at}: {log.action_type} - {log.description}")
        else:
            self.stdout.write("❌ Записей в логах нет")

        # Статистика по типам действий
        from django.db.models import Count
        stats = ActionLog.objects.values('action_type').annotate(count=Count('id')).order_by('-count')
        if stats:
            self.stdout.write("📈 Статистика по типам действий:")
            for stat in stats:
                self.stdout.write(f"   {stat['action_type']}: {stat['count']}")

        self.stdout.write(
            self.style.SUCCESS("✅ Проверка завершена!")
        )