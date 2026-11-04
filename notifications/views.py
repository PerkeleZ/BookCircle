from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification
from .serializers import NotificationSerializer


class NotificationList(generics.ListAPIView):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)


class UnreadCount(APIView):
    def get(self, request):
        return Response({'count': Notification.objects.filter(user=request.user, is_read=False).count()})


class MarkRead(APIView):
    """POST {"ids": [1, 2]} или {"all": true}."""

    def post(self, request):
        qs = Notification.objects.filter(user=request.user, is_read=False)
        if not request.data.get('all'):
            ids = [i for i in (request.data.get('ids') or []) if isinstance(i, int)]
            qs = qs.filter(id__in=ids)
        return Response({'updated': qs.update(is_read=True)})
