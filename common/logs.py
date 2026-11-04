import json
import logging


class JsonFormatter(logging.Formatter):
    """Одна строка JSON на запись — удобно для Loki / ELK / CloudWatch."""

    def format(self, record):
        data = {'ts': self.formatTime(record, '%Y-%m-%dT%H:%M:%S%z'), 'level': record.levelname,
                'logger': record.name, 'msg': record.getMessage()}
        for extra in ('request_id', 'user_id', 'status', 'ms', 'method', 'path'):
            if hasattr(record, extra):
                data[extra] = getattr(record, extra)
        if record.exc_info:
            data['exc'] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)
