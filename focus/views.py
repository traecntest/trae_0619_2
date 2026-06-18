import time
from datetime import datetime

from django.contrib.auth.models import User
from django.db import transaction, IntegrityError
from django.db.models import F
from rest_framework import status, viewsets, mixins
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import FocusSession
from .serializers import (
    FocusSessionCreateSerializer,
    FocusSessionSerializer,
    UserRegistrationSerializer,
    UserSerializer,
)
from .time_engine import VirtualTimeEngine
from .heartbeat_store import heartbeat_store


@api_view(["POST"])
@permission_classes([AllowAny])
def register_view(request):
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {"token": token.key, "user": UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    from django.contrib.auth import authenticate
    username = request.data.get("username")
    password = request.data.get("password")
    user = authenticate(username=username, password=password)
    if user is None:
        return Response({"error": "用户名或密码错误"}, status=status.HTTP_401_UNAUTHORIZED)
    token, _ = Token.objects.get_or_create(user=user)
    return Response({"token": token.key, "user": UserSerializer(user).data})


class FocusSessionViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    serializer_class = FocusSessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return FocusSession.objects.filter(user=self.request.user).select_related("user")

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = FocusSessionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        existing = (
            FocusSession.objects.select_for_update()
            .filter(user=user, status__in=[FocusSession.STATUS_RUNNING, FocusSession.STATUS_PAUSED])
            .order_by("-created_at")
            .first()
        )
        if existing is not None:
            engine = VirtualTimeEngine
            state = engine.build_state_payload(existing)
            return Response(
                {"detail": "已有进行中的会话", "session": state},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            session = FocusSession.objects.create(
                user=user,
                title=serializer.validated_data.get("title", "专注会话"),
                speed_rate=serializer.validated_data.get("speed_rate", 10.0),
                total_planned_virtual_seconds=serializer.validated_data[
                    "total_planned_virtual_seconds"
                ],
                start_real_timestamp=time.time(),
                status=FocusSession.STATUS_RUNNING,
            )
        except IntegrityError:
            return Response(
                {"error": "创建会话失败，请重试"},
                status=status.HTTP_409_CONFLICT,
            )

        heartbeat_store.set_session_snapshot(
            session.id,
            {
                "status": session.status,
                "speed_rate": session.speed_rate,
                "start_real_timestamp": session.start_real_timestamp,
                "accumulated_virtual_seconds": session.accumulated_virtual_seconds,
                "last_pause_real_timestamp": session.last_pause_real_timestamp,
            },
        )

        state = VirtualTimeEngine.build_state_payload(session)
        return Response(state, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="active")
    @transaction.atomic
    def active(self, request):
        user = request.user
        session = (
            FocusSession.objects.select_for_update()
            .filter(user=user, status__in=[FocusSession.STATUS_RUNNING, FocusSession.STATUS_PAUSED])
            .order_by("-created_at")
            .first()
        )
        if session is None:
            return Response({"detail": "无进行中的会话"}, status=status.HTTP_404_NOT_FOUND)
        state = VirtualTimeEngine.build_state_payload(session)
        return Response(state)

    @action(detail=True, methods=["post"], url_path="heartbeat")
    def heartbeat(self, request, pk=None):
        session = self.get_object()
        heartbeat_store.record_heartbeat(session.id, request.data)
        state = VirtualTimeEngine.build_state_payload(session)
        return Response(state)

    @action(detail=True, methods=["post"], url_path="pause")
    @transaction.atomic
    def pause(self, request, pk=None):
        session = self.get_object()
        locked = (
            FocusSession.objects.select_for_update()
            .filter(pk=session.pk, user=request.user)
            .first()
        )
        if locked is None:
            return Response({"error": "无权限"}, status=status.HTTP_403_FORBIDDEN)

        if locked.status == FocusSession.STATUS_COMPLETED:
            return Response({"error": "会话已结束"}, status=status.HTTP_400_BAD_REQUEST)

        if locked.status == FocusSession.STATUS_PAUSED:
            return Response(VirtualTimeEngine.build_state_payload(locked))

        now_real = time.time()
        virtual_seconds = VirtualTimeEngine.compute_current_virtual_seconds(locked, now_real)
        locked.accumulated_virtual_seconds = virtual_seconds
        locked.last_pause_real_timestamp = now_real
        locked.status = FocusSession.STATUS_PAUSED
        locked.save()

        heartbeat_store.set_session_snapshot(
            locked.id,
            {
                "status": locked.status,
                "accumulated_virtual_seconds": locked.accumulated_virtual_seconds,
                "last_pause_real_timestamp": locked.last_pause_real_timestamp,
            },
        )

        state = VirtualTimeEngine.build_state_payload(locked, now_real)
        return Response(state)

    @action(detail=True, methods=["post"], url_path="resume")
    @transaction.atomic
    def resume(self, request, pk=None):
        session = self.get_object()
        locked = (
            FocusSession.objects.select_for_update()
            .filter(pk=session.pk, user=request.user)
            .first()
        )
        if locked is None:
            return Response({"error": "无权限"}, status=status.HTTP_403_FORBIDDEN)

        if locked.status == FocusSession.STATUS_COMPLETED:
            return Response({"error": "会话已结束"}, status=status.HTTP_400_BAD_REQUEST)

        if locked.status == FocusSession.STATUS_RUNNING:
            return Response(VirtualTimeEngine.build_state_payload(locked))

        locked.status = FocusSession.STATUS_RUNNING
        locked.last_pause_real_timestamp = time.time()
        locked.save()

        heartbeat_store.set_session_snapshot(
            locked.id,
            {
                "status": locked.status,
                "last_pause_real_timestamp": locked.last_pause_real_timestamp,
            },
        )

        return Response(VirtualTimeEngine.build_state_payload(locked))

    @action(detail=True, methods=["post"], url_path="finish")
    @transaction.atomic
    def finish(self, request, pk=None):
        session = self.get_object()
        locked = (
            FocusSession.objects.select_for_update()
            .filter(pk=session.pk, user=request.user)
            .first()
        )
        if locked is None:
            return Response({"error": "无权限"}, status=status.HTTP_403_FORBIDDEN)

        if locked.status == FocusSession.STATUS_COMPLETED:
            return Response(VirtualTimeEngine.build_state_payload(locked))

        now_real = time.time()
        virtual_seconds = VirtualTimeEngine.compute_current_virtual_seconds(locked, now_real)
        locked.accumulated_virtual_seconds = virtual_seconds
        locked.last_pause_real_timestamp = now_real
        locked.status = FocusSession.STATUS_COMPLETED
        locked.completed_at = datetime.now()
        locked.save()

        heartbeat_store.clear_session(locked.id)

        return Response(VirtualTimeEngine.build_state_payload(locked, now_real))
