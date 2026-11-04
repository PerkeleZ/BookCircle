from django.db import transaction
from django.db.models import Count, Exists, OuterRef
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from common.exceptions import Conflict
from notifications.services import notify

from .models import Meeting, MeetingParticipant
from .serializers import MeetingDetailSerializer, MeetingSerializer


def meeting_qs(user):
    qs = Meeting.objects.select_related('book', 'organizer').annotate(n_participants=Count('participants', distinct=True))
    if user.is_authenticated:
        qs = qs.annotate(joined=Exists(MeetingParticipant.objects.filter(meeting=OuterRef('pk'), user=user)))
    return qs


def meeting_data(request, pk):
    return MeetingSerializer(meeting_qs(request.user).get(pk=pk), context={'request': request}).data


class MeetingList(generics.ListCreateAPIView):
    serializer_class = MeetingSerializer

    def get_queryset(self):
        p, now = self.request.query_params, timezone.now()
        qs = meeting_qs(self.request.user)
        if (b := p.get('book', '')).isdigit():
            qs = qs.filter(book_id=int(b))
        when = p.get('when', 'upcoming')
        if when == 'past':
            return qs.filter(starts_at__lt=now).order_by('-starts_at')
        if when == 'mine':
            return qs.filter(starts_at__gte=now, joined=True).order_by('starts_at')
        return qs.filter(starts_at__gte=now, is_cancelled=False).order_by('starts_at')

    def perform_create(self, s):
        with transaction.atomic():
            m = s.save(organizer=self.request.user)
            MeetingParticipant.objects.create(meeting=m, user=self.request.user)  # организатор идёт сам


class MeetingDetail(generics.RetrieveUpdateAPIView):
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_queryset(self):
        return meeting_qs(self.request.user)

    def get_serializer_class(self):
        return MeetingDetailSerializer if self.request.method == 'GET' else MeetingSerializer

    def perform_update(self, s):
        m, u = s.instance, self.request.user
        if not (m.organizer_id == u.id or u.is_moderator):
            raise PermissionDenied('Редактировать встречу может только организатор.')
        if m.is_cancelled or m.starts_at < timezone.now():
            raise Conflict('Отменённую или прошедшую встречу изменить нельзя.')
        cap = s.validated_data.get('capacity', m.capacity)
        if cap is not None and cap < m.participants.count():
            raise ValidationError({'capacity': ['Участников уже больше, чем мест.']})
        s.save()


class MeetingJoin(APIView):
    def post(self, request, pk):
        with transaction.atomic():
            m = get_object_or_404(Meeting.objects.select_for_update(), pk=pk)  # блокировка: места не «перепродаются»
            if m.is_cancelled:
                raise Conflict('Встреча отменена.')
            if m.starts_at < timezone.now():
                raise Conflict('Встреча уже прошла.')
            if m.participants.filter(user=request.user).exists():
                raise Conflict('Вы уже участвуете во встрече.')
            if m.capacity is not None and m.participants.count() >= m.capacity:
                raise Conflict('Свободных мест не осталось.')
            MeetingParticipant.objects.create(meeting=m, user=request.user)
        return Response(meeting_data(request, pk))


class MeetingLeave(APIView):
    def post(self, request, pk):
        m = get_object_or_404(Meeting, pk=pk)
        if m.organizer_id == request.user.id:
            raise Conflict('Организатор не может покинуть встречу — отмените её.')
        deleted, _ = MeetingParticipant.objects.filter(meeting=m, user=request.user).delete()
        if not deleted:
            raise Conflict('Вы не участвуете в этой встрече.')
        return Response(meeting_data(request, pk))


class MeetingCancel(APIView):
    def post(self, request, pk):
        m = get_object_or_404(Meeting, pk=pk)
        if not (m.organizer_id == request.user.id or request.user.is_moderator):
            raise PermissionDenied('Отменить встречу может только организатор или модератор.')
        if m.is_cancelled:
            raise Conflict('Встреча уже отменена.')
        m.is_cancelled = True
        m.save(update_fields=['is_cancelled'])
        for p in m.participants.select_related('user'):
            if p.user_id != request.user.id:
                notify(p.user, 'meeting_cancelled', f'Встреча «{m.title}» отменена', f'Запланированная на {timezone.localtime(m.starts_at):%d.%m.%Y %H:%M} встреча отменена.', '#/meetings')
        return Response(meeting_data(request, pk))
