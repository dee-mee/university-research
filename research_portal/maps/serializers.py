
from rest_framework import serializers
from .models import LocationMarker, EnvironmentalData, UserMarkerAnnotation, AlertThreshold, DataSource

class DataSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataSource
        fields = ['id', 'name', 'url', 'description', 'attribution_text']

class EnvironmentalDataSerializer(serializers.ModelSerializer):
    data_source_info = DataSourceSerializer(source='data_source', read_only=True)
    
    class Meta:
        model = EnvironmentalData
        fields = '__all__'
        
class UserMarkerAnnotationSerializer(serializers.ModelSerializer):
    username = serializers.ReadOnlyField(source='user.username')
    
    class Meta:
        model = UserMarkerAnnotation
        fields = ['id', 'username', 'text', 'created_at', 'updated_at']

class AlertThresholdSerializer(serializers.ModelSerializer):
    metric_display = serializers.CharField(source='get_metric_display', read_only=True)
    condition_display = serializers.CharField(source='get_condition_display', read_only=True)
    
    class Meta:
        model = AlertThreshold
        fields = ['id', 'metric', 'metric_display', 'condition', 'condition_display', 'value', 'active']

class LocationMarkerSerializer(serializers.ModelSerializer):
    latest_data = serializers.SerializerMethodField()
    annotations = UserMarkerAnnotationSerializer(many=True, read_only=True)
    alert_thresholds = serializers.SerializerMethodField()
    
    class Meta:
        model = LocationMarker
        fields = ['id', 'name', 'latitude', 'longitude', 'elevation', 'land_use_classification',
                 'ecological_zone', 'conservation_status', 'population_density', 
                 'created_at', 'updated_at', 'latest_data', 'annotations', 'alert_thresholds']
    
    def get_latest_data(self, obj):
        latest = obj.environmental_data.first()
        if latest:
            return EnvironmentalDataSerializer(latest).data
        return None
    
    def get_alert_thresholds(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            thresholds = obj.alert_thresholds.filter(user=request.user)
            return AlertThresholdSerializer(thresholds, many=True).data
        return []

class LocationMarkerDetailSerializer(LocationMarkerSerializer):
    environmental_data = serializers.SerializerMethodField()
    
    class Meta(LocationMarkerSerializer.Meta):
        fields = LocationMarkerSerializer.Meta.fields + ['environmental_data']
    
    def get_environmental_data(self, obj):
        # Get query params for filtering
        request = self.context.get('request')
        limit = 10  # Default limit
        
        if request:
            limit = int(request.query_params.get('limit', 10))
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            
            queryset = obj.environmental_data.all()
            
            if start_date:
                queryset = queryset.filter(timestamp__gte=start_date)
            if end_date:
                queryset = queryset.filter(timestamp__lte=end_date)
                
            queryset = queryset[:limit]
            return EnvironmentalDataSerializer(queryset, many=True).data
        
        return EnvironmentalDataSerializer(obj.environmental_data.all()[:limit], many=True).data