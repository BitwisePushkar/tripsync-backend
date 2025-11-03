from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiParameter
from .models import TrendingPlace, FunFact
from .serializers import (TrendingPlaceSerializer, TrendingPlaceCreateSerializer,FunFactSerializer,FunFactCreateUpdateSerializer)

class PlaceListCreateView(APIView): 
    @extend_schema(
        summary="List All Places",
        description="Get all trending places with their fun facts",
        responses={200: TrendingPlaceSerializer(many=True)})
    def get(self, request):
        places = TrendingPlace.objects.all()
        serializer = TrendingPlaceSerializer(places, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Create New Place",
        description="Create a new trending place",
        request=TrendingPlaceCreateSerializer,
        responses={201: TrendingPlaceSerializer})
    def post(self, request):
        serializer = TrendingPlaceCreateSerializer(data=request.data)
        if serializer.is_valid():
            place = serializer.save()
            response_serializer = TrendingPlaceSerializer(place)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PlaceDetailView(APIView):
    def get_place(self, place_id):
        try:
            return TrendingPlace.objects.get(id=place_id)
        except TrendingPlace.DoesNotExist:
            return None
    @extend_schema(
        summary="Get Place Details",
        description="Get a specific place with all fun facts",
        responses={200: TrendingPlaceSerializer, 404: None})
    def get(self, request, place_id):
        place = self.get_place(place_id)
        if not place:
            return Response({"error": "Place not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = TrendingPlaceSerializer(place)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Update Place",
        description="Update a trending place",
        request=TrendingPlaceCreateSerializer,
        responses={200: TrendingPlaceSerializer, 404: None})
    def put(self, request, place_id):
        place = self.get_place(place_id)
        if not place:
            return Response({"error": "Place not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = TrendingPlaceCreateSerializer(place, data=request.data)
        if serializer.is_valid():
            serializer.save()
            response_serializer = TrendingPlaceSerializer(place)
            return Response(response_serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Delete Place",
        description="Delete a place and all its fun facts",
        responses={204: None, 404: None})
    def delete(self, request, place_id):
        place = self.get_place(place_id)
        if not place:
            return Response({"error": "Place not found"}, status=status.HTTP_404_NOT_FOUND)
        place.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class FunFactListCreateView(APIView):
    @extend_schema(
        summary="List Fun Facts",
        description="Get all fun facts, optionally filter by place",
        parameters=[
            OpenApiParameter(name='place', type=int, location=OpenApiParameter.QUERY, description='Filter by place ID')
        ],
        responses={200: FunFactSerializer(many=True)})
    def get(self, request):
        place_id = request.query_params.get('place', None)
        if place_id:
            fun_facts = FunFact.objects.filter(place_id=place_id)
        else:
            fun_facts = FunFact.objects.all()
        serializer = FunFactSerializer(fun_facts, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Create Fun Fact",
        description="Add a new fun fact to a place",
        request=FunFactCreateUpdateSerializer,
        responses={201: FunFactSerializer})
    def post(self, request):
        serializer = FunFactCreateUpdateSerializer(data=request.data)
        if serializer.is_valid():
            fun_fact = serializer.save()
            response_serializer = FunFactSerializer(fun_fact)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class FunFactDetailView(APIView):
    def get_fun_fact(self, fact_id):
        try:
            return FunFact.objects.get(id=fact_id)
        except FunFact.DoesNotExist:
            return None
    @extend_schema(
        summary="Get Fun Fact",
        description="Get a specific fun fact",
        responses={200: FunFactSerializer, 404: None})
    def get(self, request, fact_id):
        fun_fact = self.get_fun_fact(fact_id)
        if not fun_fact:
            return Response({"error": "Fun fact not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = FunFactSerializer(fun_fact)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Update Fun Fact",
        description="Update a fun fact",
        request=FunFactCreateUpdateSerializer,
        responses={200: FunFactSerializer, 404: None})
    def put(self, request, fact_id):
        fun_fact = self.get_fun_fact(fact_id)
        if not fun_fact:
            return Response({"error": "Fun fact not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = FunFactCreateUpdateSerializer(fun_fact, data=request.data)
        if serializer.is_valid():
            serializer.save()
            response_serializer = FunFactSerializer(fun_fact)
            return Response(response_serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Delete Fun Fact",
        description="Delete a fun fact",
        responses={204: None, 404: None})
    def delete(self, request, fact_id):
        fun_fact = self.get_fun_fact(fact_id)
        if not fun_fact:
            return Response({"error": "Fun fact not found"}, status=status.HTTP_404_NOT_FOUND)
        fun_fact.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)