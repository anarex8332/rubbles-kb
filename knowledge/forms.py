from django import forms

from .models import Article, Collection, Section


class ArticleForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = ['title', 'content', 'section', 'status', 'allow_comments', 'article_type', 'scope', 'keywords', 'client', 'project']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['section'].queryset = Section.objects.filter(is_active=True)
        self.fields['section'].required = False
        self.fields['content'].required = True
        self.fields['article_type'].required = False

    def clean_article_type(self):
        return self.cleaned_data.get('article_type') or 'instruction'


class CollectionForm(forms.ModelForm):
    class Meta:
        model = Collection
        fields = ['title', 'description', 'role', 'project']
