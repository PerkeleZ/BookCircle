#!/usr/bin/env python
import os
import sys


def main():
    # `manage.py test` использует быстрые тестовые настройки, остальное — режим разработки
    default = 'config.settings.test' if sys.argv[1:2] == ['test'] else 'config.settings.dev'
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', default)
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
