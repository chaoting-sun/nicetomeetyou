from rest_framework.generics import ListAPIView, RetrieveAPIView

from .models import News
from .serializers import NewsDetailSerializer, NewsListSerializer


class NewsListView(ListAPIView):
    queryset = News.objects.all()
    serializer_class = NewsListSerializer


class NewsDetailView(RetrieveAPIView):
    queryset = News.objects.all()
    serializer_class = NewsDetailSerializer
