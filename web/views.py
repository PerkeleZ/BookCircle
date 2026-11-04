from django.http import Http404
from django.views.generic import TemplateView


class Index(TemplateView):
    template_name = 'web/index.html'


class Legal(TemplateView):
    PAGES = ('terms', 'privacy')

    def get_template_names(self):
        if self.kwargs['page'] not in self.PAGES:
            raise Http404
        return [f"web/{self.kwargs['page']}.html"]
