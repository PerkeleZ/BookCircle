from django.db import migrations


def create_index(apps, schema_editor):
    """PostgreSQL: GIN-индекс по триграммам ускоряет поиск «содержит» (LIKE '%…%') по каталогу на больших объёмах."""
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')
    schema_editor.execute('CREATE INDEX IF NOT EXISTS catalog_book_search_trgm ON catalog_book USING gin (search_text gin_trgm_ops)')


def drop_index(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute('DROP INDEX IF EXISTS catalog_book_search_trgm')


class Migration(migrations.Migration):
    dependencies = [('catalog', '0001_initial')]
    operations = [migrations.RunPython(create_index, drop_index)]
