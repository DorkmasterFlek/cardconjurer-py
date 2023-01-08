from rest_framework import serializers

from . import models


class SetSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Set
        fields = ['id', 'name', 'code', 'set_symbol']


class CardSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Card
        fields = ['id', 'set', 'front', 'front_art', 'front_image', 'back', 'back_art', 'back_image']
