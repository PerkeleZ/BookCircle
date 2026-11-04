"""Архитектурный тест: приложения могут зависеть только от разрешённых соседей (направление — сверху вниз).
Нарушение схемы ломает сборку, поэтому связность не «ползёт» со временем. Связь «наоборот» идёт через сигналы
(catalog.signals.book_deleting) и через реестр моделей (apps.get_model), а не через импорты."""
import ast
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

DOMAIN = {'accounts', 'catalog', 'exchange', 'reviews', 'reading', 'meetings', 'notifications'}
ALLOWED = {
    'common': set(),
    'accounts': {'common'},
    'notifications': {'common'},
    'catalog': {'common', 'notifications'},
    'exchange': {'common', 'catalog', 'notifications'},
    'reviews': {'common', 'catalog', 'notifications'},
    'reading': {'common', 'catalog', 'reviews'},
    'meetings': {'common', 'catalog', 'notifications'},
    'web': set(),
    # слой композиции и демо читают всё (листья графа: от них никто не зависит)
    'analytics': {'common'} | DOMAIN,
    'privacy': {'common'} | DOMAIN,
    'demo': {'common'} | DOMAIN,
}


def imported_apps(path, own):
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
        names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ''] if isinstance(node, ast.ImportFrom) and node.level == 0 else []
        found |= {n.split('.')[0] for n in names} & (set(ALLOWED) - {own})
    return found


class ArchitectureTests(SimpleTestCase):
    def test_apps_respect_the_dependency_graph(self):
        problems = []
        for app, allowed in ALLOWED.items():
            for path in (Path(settings.BASE_DIR) / app).rglob('*.py'):
                if 'migrations' in path.parts or path.name.startswith('test'):
                    continue
                extra = imported_apps(path, app) - allowed
                if extra:
                    problems.append(f'{path.relative_to(settings.BASE_DIR)}: {app} не должен импортировать {sorted(extra)}')
        self.assertEqual(problems, [])

    def test_every_installed_project_app_is_covered(self):
        project = {a for a in settings.INSTALLED_APPS if '.' not in a and (Path(settings.BASE_DIR) / a).is_dir()}
        self.assertEqual(project - set(ALLOWED), set())  # новое приложение нужно добавить в схему зависимостей
