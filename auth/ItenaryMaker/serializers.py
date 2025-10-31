from rest_framework import serializers
from .models import ItenaryFields

class ItenarySerializer(serializers.ModelSerializer):

    class Meta:
        model = ItenaryFields
        fields = ['tripname','current_loc','destination','trending','start_date','end_date','days','trip_type','trip_preferences','Budget']
        read_only_fields = ['tripname','destination','trending']