import sys

from django.core.mail.backends.base import BaseEmailBackend


class TerminalEmailBackend(BaseEmailBackend):
    """Печатает письмо в терминал, где запущен сервер (вместо отправки через SMTP/Gmail)."""

    def send_messages(self, messages):
        for m in messages:
            text = ('\n' + '=' * 72 + f'\nПИСЬМО (в терминал, не отправлено по почте)\nКому: {", ".join(m.to)}\n'
                    f'Тема: {m.subject}\n' + '-' * 72 + f'\n{m.body}\n' + '=' * 72 + '\n')
            try:
                print(text, flush=True)
            except UnicodeEncodeError:  # консоль с «неудобной» кодировкой (Windows)
                enc = sys.stdout.encoding or 'utf-8'
                sys.stdout.write(text.encode(enc, 'replace').decode(enc))
                sys.stdout.flush()
        return len(messages)
