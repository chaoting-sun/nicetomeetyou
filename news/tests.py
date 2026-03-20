from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from .models import News


def _create_news(n=1, **overrides):
    """Helper to create News objects for tests."""
    articles = []
    for i in range(n):
        defaults = {
            "title": f"Test Article {i}",
            "author": f"Author {i}",
            "published_at": timezone.now() - timezone.timedelta(hours=n - i),
            "source_name": "udn NBA",
            "source_url": f"https://tw-nba.udn.com/nba/story/7002/{10000 + i}",
            "content": f"<p>Content of article {i}</p>",
            "hero_image_url": f"https://example.com/img{i}.jpg",
            "hero_image_caption": f"Caption {i}",
        }
        defaults.update(overrides)
        if "source_url" in overrides and n > 1:
            defaults["source_url"] = f"{overrides['source_url']}/{i}"
        articles.append(News.objects.create(**defaults))
    return articles


class NewsListAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("news-list")

    def test_list_returns_paginated_results(self):
        _create_news(15)
        resp = self.client.get(self.url)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("count", resp.data)
        self.assertIn("results", resp.data)
        self.assertIn("next", resp.data)
        self.assertIn("previous", resp.data)
        self.assertEqual(resp.data["count"], 15)
        self.assertEqual(len(resp.data["results"]), 10)

    def test_list_excludes_content(self):
        _create_news(1)
        resp = self.client.get(self.url)

        article = resp.data["results"][0]
        self.assertNotIn("content", article)
        self.assertIn("title", article)
        self.assertIn("hero_image_url", article)

    def test_list_ordered_by_published_at_desc(self):
        articles = _create_news(3)
        resp = self.client.get(self.url)

        results = resp.data["results"]
        returned_ids = [r["id"] for r in results]
        expected_ids = [a.id for a in reversed(articles)]
        self.assertEqual(returned_ids, expected_ids)

    def test_list_empty(self):
        resp = self.client.get(self.url)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 0)
        self.assertEqual(resp.data["results"], [])


class NewsDetailAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_detail_returns_full_article(self):
        article = _create_news(1)[0]
        url = reverse("news-detail", args=[article.pk])
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["id"], article.pk)
        self.assertEqual(resp.data["title"], article.title)
        self.assertIn("content", resp.data)
        self.assertEqual(resp.data["content"], article.content)
        self.assertIn("source_url", resp.data)
        self.assertIn("created_at", resp.data)
        self.assertIn("updated_at", resp.data)

    def test_detail_404_for_nonexistent(self):
        url = reverse("news-detail", args=[99999])
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
