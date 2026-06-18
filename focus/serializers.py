from django.contrib.auth.models import User
from rest_framework import serializers
from .models import FocusSession


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email"]


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=4)

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email", ""),
            password=validated_data["password"],
        )
        return user


class FocusSessionCreateSerializer(serializers.ModelSerializer):
    total_planned_virtual_minutes = serializers.FloatField(
        write_only=True, required=False, default=60.0
    )

    class Meta:
        model = FocusSession
        fields = [
            "title",
            "speed_rate",
            "total_planned_virtual_minutes",
            "total_planned_virtual_seconds",
        ]
        read_only_fields = ["total_planned_virtual_seconds"]
        extra_kwargs = {
            "title": {"required": False},
            "speed_rate": {"required": False},
        }

    def validate_speed_rate(self, value):
        if value is None:
            return 10.0
        if value <= 0:
            raise serializers.ValidationError("speed_rate 必须大于 0")
        return value

    def validate(self, attrs):
        minutes = attrs.pop("total_planned_virtual_minutes", 60.0)
        if minutes <= 0:
            raise serializers.ValidationError("计划时长必须大于 0")
        attrs["total_planned_virtual_seconds"] = minutes * 60.0
        return attrs


class FocusSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FocusSession
        fields = [
            "id",
            "title",
            "status",
            "speed_rate",
            "start_real_timestamp",
            "last_pause_real_timestamp",
            "accumulated_virtual_seconds",
            "total_planned_virtual_seconds",
            "created_at",
            "updated_at",
            "completed_at",
        ]
