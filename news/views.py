from django.shortcuts import render
from rest_framework.generics import ListAPIView, RetrieveAPIView

from .models import News
from .serializers import NewsDetailSerializer, NewsListSerializer


class NewsListView(ListAPIView):
    queryset = News.objects.all()
    serializer_class = NewsListSerializer


class NewsDetailView(RetrieveAPIView):
    queryset = News.objects.all()
    serializer_class = NewsDetailSerializer


def news_list_page(request):
    return render(request, "news/news_list.html")


def news_detail_page(request, pk):
    return render(request, "news/news_detail.html", {"pk": pk})
